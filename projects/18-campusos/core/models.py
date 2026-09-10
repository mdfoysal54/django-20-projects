"""CampusOS — school operating system."""
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


def next_number(model, field, prefix):
    head = f"{prefix}-{timezone.localdate():%Y}-"
    last = (model.objects.filter(**{f"{field}__startswith": head})
            .order_by(f"-{field}").values_list(field, flat=True).first())
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{head}{seq:04d}"


class School(models.Model):
    name = models.CharField(max_length=160, default="CampusOS Academy")
    motto = models.CharField(max_length=160, blank=True, default="Learn with honour.")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=24, blank=True)
    address = models.CharField(max_length=240, blank=True)
    theme = models.CharField(max_length=16, default="ivory")
    language = models.CharField(max_length=8, default="en")

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Profile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        TEACHER = "teacher", "Teacher"
        ACCOUNTANT = "accountant", "Accountant"
        PARENT = "parent", "Parent"
        STUDENT = "student", "Student"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.TEACHER)
    phone = models.CharField(max_length=24, blank=True)
    theme = models.CharField(max_length=16, default="ivory")
    language = models.CharField(max_length=8, default="en")


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    starts_on = models.DateField()
    ends_on = models.DateField()
    is_current = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Klass(models.Model):
    name = models.CharField(max_length=40)
    rank = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["rank"]
        verbose_name_plural = "classes"

    def __str__(self):
        return self.name


class Section(models.Model):
    klass = models.ForeignKey(Klass, on_delete=models.CASCADE, related_name="sections")
    name = models.CharField(max_length=8)
    capacity = models.PositiveSmallIntegerField(default=40)

    class Meta:
        unique_together = [("klass", "name")]
        ordering = ["klass__rank", "name"]

    def __str__(self):
        return f"{self.klass.name}-{self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=80)
    code = models.CharField(max_length=12, unique=True)
    klass = models.ForeignKey(Klass, on_delete=models.CASCADE, related_name="subjects")

    def __str__(self):
        return f"{self.code} {self.name}"


class Guardian(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24)
    email = models.EmailField(blank=True)
    relation = models.CharField(max_length=40, default="Parent")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class Student(models.Model):
    class Status(models.TextChoices):
        APPLICANT = "app", "Applicant"
        ENROLLED = "ok", "Enrolled"
        ALUMNI = "al", "Alumni"
        LEFT = "left", "Left"

    number = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    gender = models.CharField(max_length=1, choices=[("F", "Female"), ("M", "Male"), ("O", "Other")])
    born_on = models.DateField()
    guardian = models.ForeignKey(Guardian, on_delete=models.PROTECT, related_name="children")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name="students")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.APPLICANT)
    admitted_on = models.DateField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number(Student, "number", "STU")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_absolute_url(self):
        return reverse("student_detail", kwargs={"number": self.number})

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Staff(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff")
    code = models.CharField(max_length=16, unique=True)
    designation = models.CharField(max_length=80)
    subjects = models.ManyToManyField(Subject, blank=True)
    joined_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class FeeHead(models.Model):
    name = models.CharField(max_length=80, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_recurring = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PAID = "paid", "Paid"
        PARTIAL = "part", "Partial"
        VOID = "void", "Void"

    number = models.CharField(max_length=24, unique=True, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="invoices")
    head = models.ForeignKey(FeeHead, on_delete=models.PROTECT)
    period = models.CharField(max_length=7)  # YYYY-MM
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_total = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    due_on = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number(Invoice, "number", "FEE")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("invoice_detail", kwargs={"number": self.number})

    @property
    def balance(self) -> Decimal:
        return money(self.amount - self.paid_total)

    def refresh_status(self):
        if self.status == self.Status.VOID:
            return
        self.status = self.Status.PAID if self.balance <= 0 else (
            self.Status.PARTIAL if self.paid_total > 0 else self.Status.OPEN)
        self.save(update_fields=["status"])


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=12, default="cash")
    received_on = models.DateField(default=timezone.localdate)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)


class Attendance(models.Model):
    class Mark(models.TextChoices):
        PRESENT = "P", "Present"
        ABSENT = "A", "Absent"
        LATE = "L", "Late"
        EXCUSED = "E", "Excused"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance")
    day = models.DateField()
    mark = models.CharField(max_length=1, choices=Mark.choices, default=Mark.PRESENT)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)

    class Meta:
        unique_together = [("student", "day")]


class Exam(models.Model):
    name = models.CharField(max_length=80)
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name="exams")
    held_on = models.DateField()
    max_marks = models.PositiveSmallIntegerField(default=100)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("exam_detail", kwargs={"pk": self.pk})


class Score(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="scores")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="scores")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    marks = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = [("exam", "student", "subject")]

    @property
    def grade(self) -> str:
        pct = float(self.marks) / self.exam.max_marks * 100 if self.exam.max_marks else 0
        if pct >= 80:
            return "A+"
        if pct >= 70:
            return "A"
        if pct >= 60:
            return "B"
        if pct >= 50:
            return "C"
        if pct >= 40:
            return "D"
        return "F"

    @property
    def passed(self) -> bool:
        return self.grade != "F"


class Period(models.Model):
    weekday = models.PositiveSmallIntegerField()  # 0=Mon
    slot = models.PositiveSmallIntegerField()
    starts = models.TimeField()
    ends = models.TimeField()
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="periods")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = [("section", "weekday", "slot")]
        ordering = ["weekday", "slot"]


class Book(models.Model):
    title = models.CharField(max_length=160)
    author = models.CharField(max_length=120, blank=True)
    isbn = models.CharField(max_length=20, unique=True)
    copies = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return self.title

    @property
    def available(self) -> int:
        out = self.loans.filter(returned_on__isnull=True).count()
        return max(0, self.copies - out)


class Loan(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="loans")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="loans")
    borrowed_on = models.DateField(default=timezone.localdate)
    due_on = models.DateField()
    returned_on = models.DateField(null=True, blank=True)


class Route(models.Model):
    name = models.CharField(max_length=80)
    vehicle = models.CharField(max_length=40)
    driver = models.CharField(max_length=80, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)

    def __str__(self):
        return self.name


class Rider(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="riders")
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="ride")


class Notice(models.Model):
    title = models.CharField(max_length=160)
    body = models.TextField()
    audience = models.CharField(max_length=16, default="all")
    published_on = models.DateField(default=timezone.localdate)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)


class SmsLog(models.Model):
    to = models.CharField(max_length=24)
    body = models.CharField(max_length=480)
    created = models.DateTimeField(auto_now_add=True)
