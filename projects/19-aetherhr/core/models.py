"""AetherHR — people operating system."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


class Company(models.Model):
    name = models.CharField(max_length=160, default="Aether Labs")
    tagline = models.CharField(max_length=160, default="People operations, reimagined.")
    theme = models.CharField(max_length=16, default="violet")
    language = models.CharField(max_length=8, default="en")

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        HR = "hr", "HR"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EMPLOYEE)
    theme = models.CharField(max_length=16, default="violet")
    language = models.CharField(max_length=8, default="en")
    phone = models.CharField(max_length=24, blank=True)


class Department(models.Model):
    name = models.CharField(max_length=80, unique=True)
    code = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=80)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="roles")
    level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [("department", "name")]

    def __str__(self):
        return f"{self.name} · {self.department.code}"


class Employee(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ok", "Active"
        PROBATION = "prob", "Probation"
        EXITED = "exit", "Exited"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee")
    code = models.CharField(max_length=16, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="people")
    designation = models.ForeignKey(Designation, on_delete=models.PROTECT, related_name="people")
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="reports")
    joined_on = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    basic = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    medical = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    conveyance = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def get_absolute_url(self):
        return reverse("employee_detail", kwargs={"code": self.code})

    @property
    def house_rent(self) -> Decimal:
        """Bangladesh convention: house rent allowance = 50% of basic."""
        return money(self.basic * Decimal("0.50"))

    @property
    def gross(self) -> Decimal:
        return money(self.basic + self.house_rent + self.medical + self.conveyance)


class Punch(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="punches")
    day = models.DateField(default=timezone.localdate)
    in_at = models.DateTimeField(null=True, blank=True)
    out_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("employee", "day")]

    @property
    def hours(self) -> Decimal:
        if not (self.in_at and self.out_at):
            return ZERO
        seconds = (self.out_at - self.in_at).total_seconds()
        return money(Decimal(seconds) / Decimal(3600))


class LeaveType(models.Model):
    name = models.CharField(max_length=40, unique=True)
    days_per_year = models.PositiveSmallIntegerField(default=14)
    paid = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="balances")
    kind = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()
    remaining = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = [("employee", "kind", "year")]


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pend", "Pending"
        APPROVED = "ok", "Approved"
        REJECTED = "no", "Rejected"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    kind = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="leave_decisions")

    class Meta:
        ordering = ["-starts_on"]

    def get_absolute_url(self):
        return reverse("leave_detail", kwargs={"pk": self.pk})

    @property
    def days(self) -> int:
        return (self.ends_on - self.starts_on).days + 1


class Payslip(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payslips")
    period = models.CharField(max_length=7)
    basic = models.DecimalField(max_digits=12, decimal_places=2)
    house_rent = models.DecimalField(max_digits=12, decimal_places=2)
    medical = models.DecimalField(max_digits=12, decimal_places=2)
    conveyance = models.DecimalField(max_digits=12, decimal_places=2)
    gross = models.DecimalField(max_digits=12, decimal_places=2)
    unpaid_days = models.PositiveSmallIntegerField(default=0)
    net = models.DecimalField(max_digits=12, decimal_places=2)
    generated_on = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = [("employee", "period")]
        ordering = ["-period"]

    def get_absolute_url(self):
        return reverse("payslip_detail", kwargs={"pk": self.pk})


class JobPosting(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "shut", "Closed"

    title = models.CharField(max_length=120)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    body = models.TextField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opened_on = models.DateField(default=timezone.localdate)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("job_detail", kwargs={"pk": self.pk})


class Applicant(models.Model):
    class Stage(models.TextChoices):
        NEW = "new", "New"
        SCREEN = "scr", "Screen"
        INTERVIEW = "int", "Interview"
        OFFER = "off", "Offer"
        HIRED = "hire", "Hired"
        REJECT = "no", "Rejected"

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="applicants")
    name = models.CharField(max_length=120)
    email = models.EmailField()
    stage = models.CharField(max_length=8, choices=Stage.choices, default=Stage.NEW)
    note = models.CharField(max_length=240, blank=True)

    class Meta:
        unique_together = [("job", "email")]


class Review(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="reviews")
    period = models.CharField(max_length=7)
    rating = models.PositiveSmallIntegerField()  # 1-5
    goals = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = [("employee", "period")]


class Asset(models.Model):
    name = models.CharField(max_length=120)
    tag = models.CharField(max_length=40, unique=True)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="assets")
    acquired_on = models.DateField(default=timezone.localdate)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)


class Announcement(models.Model):
    title = models.CharField(max_length=160)
    body = models.TextField()
    published_on = models.DateField(default=timezone.localdate)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
