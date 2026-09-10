"""InvoicePro models — clients, invoices, line items and payments (Decimal money)."""
from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

TWO_PLACES = Decimal("0.01")
DEFAULT_TAX_RATE = Decimal("5.00")


def money(value) -> Decimal:
    """Round any numeric input to two decimal places, half-up (invoice convention)."""
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class Client(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=120, blank=True)
    address = models.TextField(blank=True)
    tax_id = models.CharField(max_length=40, blank=True, help_text="VAT / TIN shown on invoices.")
    default_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_TAX_RATE,
                                           validators=[MinValueValidator(0)])
    default_terms_days = models.PositiveSmallIntegerField(default=14, validators=[MinValueValidator(0)])
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["owner", "name"], name="client_name_unique_per_owner")]

    def __str__(self):
        return self.name

    @property
    def outstanding(self) -> Decimal:
        return sum((inv.balance for inv in self.invoices.filter(status__in=Invoice.OPEN_STATUSES)), Decimal("0.00"))


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Part paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"

    OPEN_STATUSES = (Status.SENT, Status.PARTIAL, Status.OVERDUE)

    number = models.CharField(max_length=20, unique=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invoices")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_TAX_RATE,
                                   validators=[MinValueValidator(0)])
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"),
                                   validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date", "-created"]
        indexes = [models.Index(fields=["owner", "status"]),
                   models.Index(fields=["status", "due_date"])]
        constraints = [models.CheckConstraint(check=models.Q(due_date__gte=models.F("issue_date")),
                                              name="invoice_due_after_issue")]

    def __str__(self):
        return f"{self.number} — {self.client.name}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._next_number()
        if not self.due_date:
            self.due_date = self.issue_date + timedelta(days=self.client.default_terms_days)
        super().save(*args, **kwargs)

    def _next_number(self) -> str:
        prefix = f"INV-{timezone.localdate():%Y}"
        last = (Invoice.objects.filter(number__startswith=prefix).order_by("-number")
                .values_list("number", flat=True).first())
        sequence = int(last.split("-")[-1]) + 1 if last else 1
        return f"{prefix}-{sequence:04d}"

    def get_absolute_url(self):
        return reverse("invoice_detail", kwargs={"number": self.number})

    # -------------------------------------------------------------- money maths
    @property
    def subtotal(self) -> Decimal:
        return money(sum((item.line_total for item in self.items.all()), Decimal("0.00")))

    @property
    def tax_amount(self) -> Decimal:
        base = self.subtotal - self.discount
        return money(base * self.tax_rate / Decimal("100"))

    @property
    def total(self) -> Decimal:
        return money(self.subtotal - self.discount + self.tax_amount)

    @property
    def paid_total(self) -> Decimal:
        return money(sum((p.amount for p in self.payments.all()), Decimal("0.00")))

    @property
    def balance(self) -> Decimal:
        return money(self.total - self.paid_total)

    @property
    def is_overdue(self) -> bool:
        return self.status in self.OPEN_STATUSES and self.due_date < timezone.localdate() and self.balance > 0

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        return (timezone.localdate() - self.due_date).days

    def payment_status(self) -> str:
        """Derived status from payments + dates — never trusted from the client."""
        if self.status in (self.Status.VOID, self.Status.DRAFT):
            return self.status
        if self.balance <= 0:
            return self.Status.PAID
        if self.paid_total > 0:
            return self.Status.PARTIAL
        if self.due_date < timezone.localdate():
            return self.Status.OVERDUE
        return self.Status.SENT

    def refresh_status(self, save=True):
        new_status = self.payment_status()
        if save and new_status != self.status:
            self.status = new_status
            self.paid_at = timezone.now() if new_status == self.Status.PAID else None
            self.save(update_fields=["status", "paid_at"])
        return new_status

    # ------------------------------------------------------------- domain ops
    @transaction.atomic
    def mark_sent(self):
        if self.status == self.Status.VOID:
            raise ValueError("A void invoice cannot be sent.")
        if not self.items.exists():
            raise ValueError("Add at least one line item before sending.")
        self.status = self.Status.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])
        return self

    @transaction.atomic
    def void(self):
        self.status = self.Status.VOID
        self.save(update_fields=["status"])
        return self

    @transaction.atomic
    def record_payment(self, amount, method="bank", reference="", note=""):
        """Record a payment, refusing nonsense amounts and never overpaying silently."""
        amount = money(amount)
        if amount <= 0:
            return None, "Payments must be greater than zero."
        if self.status == self.Status.VOID:
            return None, "This invoice is void."
        if self.status == self.Status.DRAFT:
            return None, "Send the invoice before recording payments."
        if amount > self.balance:
            return None, (f"That is more than the outstanding balance of {self.balance}. "
                          f"Record {self.balance} instead.")
        locked = Invoice.objects.select_for_update().get(pk=self.pk)
        payment = Payment.objects.create(invoice=locked, amount=amount, method=method,
                                         reference=reference, note=note, recorded_by_id=locked.owner_id)
        self.refresh_from_db()
        with transaction.atomic():
            self.status = self.payment_status()
            self.paid_at = timezone.now() if self.status == self.Status.PAID else None
            self.save(update_fields=["status", "paid_at"])
        return payment, None


class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1.00"),
                                   validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.description} × {self.quantity}"

    @property
    def line_total(self) -> Decimal:
        return money(self.quantity * self.unit_price)


class Payment(models.Model):
    class Method(models.TextChoices):
        BANK = "bank", "Bank transfer"
        CARD = "card", "Card"
        CASH = "cash", "Cash"
        MOBILE = "mobile", "Mobile wallet"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=6, choices=Method.choices, default=Method.BANK)
    reference = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    related_name="recorded_payments")
    paid_on = models.DateField(default=timezone.localdate)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-created"]

    def __str__(self):
        return f"{self.invoice.number}: {self.amount}"

    def save(self, *args, **kwargs):
        self.amount = money(self.amount)
        super().save(*args, **kwargs)


class Expense(models.Model):
    """Freelancer-side expenses, so the dashboard can show a real net figure."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    description = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    category = models.CharField(max_length=40, default="General")
    incurred_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-incurred_on"]

    def __str__(self):
        return f"{self.description}: {self.amount}"
