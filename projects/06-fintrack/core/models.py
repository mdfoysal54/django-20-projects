"""FinTrack data models — accounts, categories, transactions, budgets.

Money discipline, enforced structurally:
  * every amount is Decimal(12,2) — never a float;
  * transaction direction is a sign convention: expenses are negative,
    income positive, transfers are two linked rows;
  * budgets are unique per (user, category, month) so a month can't be
    double-budgeted;
  * balances are always derived from transactions, never stored.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


class Account(models.Model):
    class Kind(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank account"
        CARD = "card", "Credit card"
        MOBILE = "mobile", "Mobile wallet"
        SAVINGS = "savings", "Savings"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.BANK)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="USD")
    icon = models.CharField(max_length=8, default="🏦")
    archived = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("user", "name")

    def __str__(self):
        return f"{self.icon} {self.name}"

    @property
    def balance(self) -> Decimal:
        """Opening balance + every transaction on this account (derived)."""
        movement = self.transactions.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
        return self.opening_balance + movement

    @property
    def is_negative(self) -> bool:
        return self.balance < 0


class Category(models.Model):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=7, choices=Kind.choices, default=Kind.EXPENSE)
    icon = models.CharField(max_length=8, default="🧾")
    color = models.CharField(max_length=7, default="#4f46e5")

    class Meta:
        ordering = ["kind", "name"]
        unique_together = ("user", "name", "kind")
        verbose_name_plural = "Categories"

    def __str__(self):
        return f"{self.icon} {self.name}"

    def spent_in_month(self, year: int, month: int) -> Decimal:
        """Sum of expense magnitudes in a month (positive number)."""
        total = self.transactions.filter(
            date__year=year, date__month=month, amount__lt=0
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
        return abs(total)


class Transaction(models.Model):
    class Kind(models.TextChoices):
        EXPENSE = "expense", "Expense"
        INCOME = "income", "Income"
        TRANSFER = "transfer", "Transfer"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.EXPENSE)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Expenses are stored as negative amounts, income as positive.",
    )
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField(default=timezone.localdate)
    # Transfer linkage (both legs share a group id)
    transfer_group = models.CharField(max_length=36, blank=True, db_index=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-pk"]
        indexes = [models.Index(fields=["user", "-date"])]

    def __str__(self):
        return f"{self.date} · {self.note or self.get_kind_display()} · {self.amount}"

    def get_absolute_url(self):
        return reverse("transaction_detail", kwargs={"pk": self.pk})

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount == 0:
            errors["amount"] = "Amount cannot be zero."
        if self.date and self.date > timezone.localdate():
            errors["date"] = "You cannot record a transaction in the future."
        if self.kind == self.Kind.EXPENSE and self.amount and self.amount > 0:
            errors["amount"] = "Expense amounts are entered as positive values and stored as negative."
        if self.kind == self.Kind.INCOME and self.amount and self.amount < 0:
            errors["amount"] = "Income amounts must be positive."
        if self.category and self.kind != self.Kind.TRANSFER:
            wanted = Category.Kind.EXPENSE if self.kind == self.Kind.EXPENSE else Category.Kind.INCOME
            if self.category.kind != wanted:
                errors["category"] = f"Pick a {wanted} category for a {self.kind} transaction."
        if errors:
            raise ValidationError(errors)

    @property
    def signed_amount(self) -> Decimal:
        return self.amount

    @property
    def absolute_amount(self) -> Decimal:
        return abs(self.amount)

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @classmethod
    def create_transfer(cls, *, user, from_account, to_account, amount: Decimal, note="", date_=None):
        """Two linked rows, same transfer_group — atomic and balanced."""

        if amount <= 0:
            raise ValidationError("Transfer amount must be positive.")
        if from_account.pk == to_account.pk:
            raise ValidationError("Pick two different accounts.")
        date_ = date_ or timezone.localdate()
        group = uuid.uuid4().hex
        with transaction.atomic():
            out = cls.objects.create(
                user=user, account=from_account, kind=cls.Kind.TRANSFER,
                amount=-amount, note=note or f"Transfer to {to_account.name}",
                date=date_, transfer_group=group,
            )
            in_ = cls.objects.create(
                user=user, account=to_account, kind=cls.Kind.TRANSFER,
                amount=amount, note=note or f"Transfer from {from_account.name}",
                date=date_, transfer_group=group,
            )
        return out, in_


class Budget(models.Model):
    """Monthly spending ceiling for one category (per user)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="budgets")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(choices=[(m, date(2000, m, 1).strftime("%B")) for m in range(1, 13)])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "category", "year", "month")
        ordering = ["-year", "-month", "category__name"]

    def __str__(self):
        return f"{self.category.name} · {self.month:02d}/{self.year} · {self.amount}"

    def clean(self):
        if self.amount is not None and self.amount <= 0:
            raise ValidationError({"amount": "Budget must be a positive amount."})
        if self.category and self.category.kind != Category.Kind.EXPENSE:
            raise ValidationError({"category": "Budgets apply to expense categories only."})

    @property
    def spent(self) -> Decimal:
        return self.category.spent_in_month(self.year, self.month)

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.spent

    @property
    def usage_percent(self) -> int:
        if not self.amount:
            return 0
        return min(round(self.spent * 100 / self.amount), 999)

    @property
    def state(self) -> str:
        """'ok' | 'warn' (≥80%) | 'over' (≥100%)."""
        percent = self.usage_percent
        if percent >= 100:
            return "over"
        if percent >= 80:
            return "warn"
        return "ok"

    @property
    def state_badge(self) -> str:
        return {"ok": "badge-ok", "warn": "badge-warn", "over": "badge-bad"}[self.state]
