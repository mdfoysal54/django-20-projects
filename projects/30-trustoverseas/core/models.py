"""Trust Overseas Ltd — visa & recruitment ERP models."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

TWO = Decimal("0.01")
ZERO = Decimal("0.00")
PASSPORT_MIN_DAYS = 190
MEDICAL_VALID_DAYS = 60


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(TWO, rounding=ROUND_HALF_UP)


def next_number(model, field: str, prefix: str, width: int = 5) -> str:
    year = timezone.localdate().strftime("%Y")
    head = f"{prefix}-{year}-"
    last = (model.objects.filter(**{f"{field}__startswith": head})
            .order_by(f"-{field}").values_list(field, flat=True).first())
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{head}{seq:0{width}d}"


class TimeStamped(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ================================================================= org
class Branch(TimeStamped):
    name = models.CharField(max_length=120)
    legal_name = models.CharField(max_length=200, default="Trust Overseas Ltd")
    trade_license = models.CharField(max_length=80, unique=True)
    tax_trn = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=3, default="BGD")
    city = models.CharField(max_length=80, default="Dhaka")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    currency = models.CharField(max_length=3, default="BDT")
    is_hq = models.BooleanField(default=False)
    theme = models.CharField(max_length=16, default="void")

    def __str__(self):
        return self.name

    @classmethod
    def hq(cls) -> "Branch":
        obj = cls.objects.filter(is_hq=True).first()
        if obj:
            return obj
        obj, _ = cls.objects.get_or_create(
            trade_license="TOL-DHK-001",
            defaults={"name": "Dhaka HQ", "legal_name": "Trust Overseas Ltd",
                      "city": "Dhaka", "is_hq": True},
        )
        return obj


class Department(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=80)

    class Meta:
        unique_together = [("branch", "name")]

    def __str__(self):
        return f"{self.branch.name} / {self.name}"


class Staff(TimeStamped):
    class Role(models.TextChoices):
        SUPER = "super", "Super admin"
        MANAGER = "manager", "Branch manager"
        ACCOUNTANT = "accountant", "Accountant"
        CASE = "case", "Case manager"
        COLLECTOR = "collector", "Document collector"
        PRO = "pro", "PRO / runner"
        RECEPTION = "reception", "Receptionist"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "susp", "Suspended"
        RESIGNED = "res", "Resigned"
        TERM = "term", "Terminated"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="staff")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=20, unique=True)
    designation = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CASE)
    phone = models.CharField(max_length=30, blank=True)
    nid = models.CharField(max_length=40, blank=True)
    hire_date = models.DateField(default=timezone.localdate)
    base_salary = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    language = models.CharField(max_length=8, default="en")
    theme = models.CharField(max_length=16, default="void")

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Attendance(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="attendance")
    day = models.DateField(default=timezone.localdate)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, default="present")
    overtime_min = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("staff", "day")]


class Leave(TimeStamped):
    class Kind(models.TextChoices):
        PAID = "paid", "Paid"
        SICK = "sick", "Sick"
        CASUAL = "cas", "Casual"
        UNPAID = "unp", "Unpaid"
        HAJJ = "hajj", "Hajj / Umrah"

    class Status(models.TextChoices):
        PENDING = "pend", "Pending"
        OK = "ok", "Approved"
        NO = "no", "Rejected"

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name="leaves")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.CASUAL)
    start = models.DateField()
    end = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


class Payroll(TimeStamped):
    staff = models.ForeignKey(Staff, on_delete=models.PROTECT, related_name="payrolls")
    period = models.CharField(max_length=7)  # YYYY-MM
    base = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    housing = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    transport = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    commission = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    net = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=12, default="draft")

    class Meta:
        unique_together = [("staff", "period")]


# ================================================================= CRM
class SubAgent(TimeStamped):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="agent_desk",
    )
    name = models.CharField(max_length=150)
    contact = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    district = models.CharField(max_length=80, blank=True)
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    commission_value = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    commission_model = models.CharField(max_length=16, default="flat")
    is_locked = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @property
    def receivable(self) -> Decimal:
        from django.db.models import Sum
        due = (self.invoices.aggregate(s=Sum("grand_total"))["s"] or ZERO) - (
            self.invoices.aggregate(s=Sum("paid_amount"))["s"] or ZERO)
        return money(due)


class Client(TimeStamped):
    class Gender(models.TextChoices):
        M = "m", "Male"
        F = "f", "Female"
        O = "o", "Other"

    class KYC(models.TextChoices):
        NONE = "none", "Unverified"
        PEND = "pend", "Pending review"
        OK = "ok", "Fully verified"
        BAN = "ban", "Blacklisted"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="client_profile",
    )
    code = models.CharField(max_length=24, unique=True, editable=False)
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    father_name = models.CharField(max_length=80, blank=True)
    mother_name = models.CharField(max_length=80, blank=True)
    gender = models.CharField(max_length=4, choices=Gender.choices, default=Gender.M)
    dob = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=3, default="BGD")
    phone = models.CharField(max_length=30)
    whatsapp = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    district = models.CharField(max_length=80, blank=True)
    address = models.TextField(blank=True)
    education = models.CharField(max_length=40, blank=True)
    trade = models.CharField(max_length=80, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=40, default="walk-in")
    agent = models.ForeignKey(SubAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name="clients")
    desk = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="clients")
    kyc = models.CharField(max_length=8, choices=KYC.choices, default=KYC.NONE)
    blacklist_reason = models.CharField(max_length=200, blank=True)
    pin = models.CharField(max_length=6, blank=True)  # tracking OTP

    class Meta:
        ordering = ["-id"]

    def save(self, *a, **k):
        if not self.code:
            self.code = next_number(Client, "code", "CL")
        super().save(*a, **k)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_absolute_url(self):
        return reverse("client_detail", kwargs={"code": self.code})


class Dependent(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="dependents")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    relation = models.CharField(max_length=20, default="spouse")
    dob = models.DateField(null=True, blank=True)
    passport_number = models.CharField(max_length=30, blank=True)
    on_visa = models.BooleanField(default=False)


class Passport(TimeStamped):
    class Loc(models.TextChoices):
        CLIENT = "client", "With client"
        VAULT = "vault", "Office vault"
        RUNNER = "runner", "Field runner"
        NOTARY = "notary", "Notary"
        MOFA = "mofa", "Foreign affairs"
        EMBASSY = "emb", "Embassy / VFS"
        COURIER = "cour", "Courier"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="passports")
    number = models.CharField(max_length=30, unique=True)
    issuing_country = models.CharField(max_length=3, default="BGD")
    issue_date = models.DateField()
    expiry_date = models.DateField()
    place_of_issue = models.CharField(max_length=80, blank=True)
    blank_pages = models.PositiveSmallIntegerField(default=8)
    location = models.CharField(max_length=10, choices=Loc.choices, default=Loc.VAULT)
    envelope = models.CharField(max_length=40, blank=True)
    carrier = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse("passport_detail", kwargs={"number": self.number})

    @property
    def days_left(self) -> int:
        return (self.expiry_date - timezone.localdate()).days

    @property
    def needs_renewal(self) -> bool:
        return self.days_left < PASSPORT_MIN_DAYS


class CustodyEvent(TimeStamped):
    passport = models.ForeignKey(Passport, on_delete=models.CASCADE, related_name="custody")
    from_loc = models.CharField(max_length=10)
    to_loc = models.CharField(max_length=10)
    note = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)


# ================================================================= cases
class VisaCase(TimeStamped):
    class Stage(models.TextChoices):
        INQ = "inq", "Inquiry"
        SIGN = "sign", "Agreement signed"
        DOCS = "docs", "Documents received"
        ATTEST = "att", "Attestation"
        MED_SCHED = "msched", "Medical scheduled"
        MED_OK = "mok", "Medical cleared"
        PORTAL = "port", "Portal submitted"
        EMBASSY = "emb", "Embassy / VFS"
        ISSUED = "iss", "Visa issued"
        FLIGHT = "fly", "Flight booked"
        ARRIVED = "arr", "Arrived"
        POST = "post", "Post-arrival"
        DONE = "done", "Closed"
        REJ = "rej", "Rejected / archived"

    class Priority(models.TextChoices):
        NORMAL = "n", "Normal"
        URGENT = "u", "Urgent"
        EMER = "e", "Emergency"

    number = models.CharField(max_length=28, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="cases")
    passport = models.ForeignKey(Passport, on_delete=models.PROTECT, related_name="cases")
    agent = models.ForeignKey(SubAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    officer = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True, related_name="cases")
    destination = models.CharField(max_length=3, default="SAU")
    visa_category = models.CharField(max_length=40, default="Work")
    job_title = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=8, choices=Stage.choices, default=Stage.INQ)
    priority = models.CharField(max_length=2, choices=Priority.choices, default=Priority.NORMAL)
    sla_date = models.DateField(null=True, blank=True)
    closed_on = models.DateField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="cases")

    class Meta:
        ordering = ["-id"]

    def save(self, *a, **k):
        if not self.number:
            self.number = next_number(VisaCase, "number", "CAS")
        super().save(*a, **k)

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse("case_detail", kwargs={"number": self.number})


class CaseDocument(TimeStamped):
    class Status(models.TextChoices):
        PEND = "pend", "Pending"
        OK = "ok", "Approved"
        ILL = "ill", "Rejected illegible"
        FAKE = "fake", "Rejected fake"

    case = models.ForeignKey(VisaCase, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=40)
    filename = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PEND)
    note = models.CharField(max_length=200, blank=True)


class Attestation(TimeStamped):
    case = models.ForeignKey(VisaCase, on_delete=models.CASCADE, related_name="attestations")
    certificate = models.CharField(max_length=150)
    authority = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=1)
    consignment = models.CharField(max_length=80, blank=True)
    submitted_on = models.DateField(null=True, blank=True)
    expected_on = models.DateField(null=True, blank=True)
    cleared_on = models.DateField(null=True, blank=True)
    gov_fee = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    cleared = models.BooleanField(default=False)


class Medical(TimeStamped):
    class Result(models.TextChoices):
        SCHED = "sched", "Scheduled"
        FIT = "fit", "Fit"
        UNFIT = "unfit", "Unfit"
        HELD = "held", "Held under review"

    case = models.OneToOneField(VisaCase, on_delete=models.CASCADE, related_name="medical")
    kind = models.CharField(max_length=24, default="GAMCA_Wafid")
    slip = models.CharField(max_length=80, blank=True)
    clinic = models.CharField(max_length=150, blank=True)
    appointment = models.DateField(null=True, blank=True)
    result = models.CharField(max_length=8, choices=Result.choices, default=Result.SCHED)
    unfit_reason = models.CharField(max_length=80, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)

    @property
    def days_left(self) -> int | None:
        if not self.expires_on:
            return None
        return (self.expires_on - timezone.localdate()).days

    @property
    def is_live(self) -> bool:
        return self.result == self.Result.FIT and self.days_left is not None and self.days_left >= 5


class PortalSubmission(TimeStamped):
    case = models.ForeignKey(VisaCase, on_delete=models.CASCADE, related_name="portals")
    portal = models.CharField(max_length=40)  # Qiwa, Enjaz, MOHRE, GDRFA, ICP, Metrash2, PAM
    application_no = models.CharField(max_length=80, blank=True)
    sponsor = models.CharField(max_length=120, blank=True)
    status_raw = models.CharField(max_length=80, blank=True)
    submitted_on = models.DateTimeField(null=True, blank=True)


class Lead(TimeStamped):
    class Status(models.TextChoices):
        NEW = "new", "Inquiry"
        QUOTE = "quote", "Quoted"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    destination = models.CharField(max_length=3, default="SAU")
    visa_category = models.CharField(max_length=40, default="Work")
    source = models.CharField(max_length=40, default="walk-in")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.NEW)
    note = models.CharField(max_length=200, blank=True)
    desk = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)


# ================================================================= accounts
class Account(models.Model):
    class Kind(models.TextChoices):
        ASSET = "asset", "Asset"
        LIAB = "liab", "Liability"
        EQUITY = "eq", "Equity"
        REV = "rev", "Revenue"
        DCOST = "dcost", "Direct expense"
        OPEX = "opex", "Operating expense"

    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def balance(self) -> Decimal:
        debit = self.debits.aggregate(s=models.Sum("amount"))["s"] or ZERO
        credit = self.credits.aggregate(s=models.Sum("amount"))["s"] or ZERO
        if self.kind in (self.Kind.ASSET, self.Kind.DCOST, self.Kind.OPEX):
            return money(debit - credit)
        return money(credit - debit)


class Invoice(TimeStamped):
    class Status(models.TextChoices):
        OPEN = "open", "Unpaid"
        PART = "part", "Partially paid"
        PAID = "paid", "Fully paid"
        BAD = "bad", "Bad debt"

    number = models.CharField(max_length=28, unique=True, editable=False)
    case = models.ForeignKey(VisaCase, on_delete=models.PROTECT, related_name="invoices")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    agent = models.ForeignKey(SubAgent, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    issued_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField()
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    revenue_recognized = models.BooleanField(default=False)

    def save(self, *a, **k):
        if not self.number:
            self.number = next_number(Invoice, "number", "INV")
        super().save(*a, **k)

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse("invoice_detail", kwargs={"number": self.number})

    @property
    def balance_due(self) -> Decimal:
        return money(self.grand_total - self.paid_amount)

    def refresh_status(self):
        if self.balance_due <= 0:
            self.status = self.Status.PAID
        elif self.paid_amount > 0:
            self.status = self.Status.PART
        else:
            self.status = self.Status.OPEN
        self.save(update_fields=["status", "paid_amount"])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=160)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("1"))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=ZERO)

    @property
    def line_total(self) -> Decimal:
        return money(self.unit_price * self.qty)


class JournalLine(TimeStamped):
    batch = models.UUIDField()
    booked_on = models.DateField(default=timezone.localdate)
    debit = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="debits")
    credit = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="credits")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    case = models.ForeignKey(VisaCase, on_delete=models.SET_NULL, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True)
    narration = models.CharField(max_length=240)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-booked_on", "-id"]


class Receipt(TimeStamped):
    number = models.CharField(max_length=28, unique=True, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="receipts")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=16, default="cash")
    reference = models.CharField(max_length=80, blank=True)
    collected_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *a, **k):
        if not self.number:
            self.number = next_number(Receipt, "number", "REC")
        super().save(*a, **k)


class PettyCash(TimeStamped):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="petty")
    requested_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, related_name="petty_out")
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    purpose = models.CharField(max_length=200)
    booked_on = models.DateField(default=timezone.localdate)


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    verb = models.CharField(max_length=40)
    model = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40, blank=True)
    detail = models.CharField(max_length=240, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]
