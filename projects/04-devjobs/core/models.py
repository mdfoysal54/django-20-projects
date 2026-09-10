"""DevJobs data models — companies, job posts, applications, saved jobs.

Domain rules worth noting:
  * a candidate can apply to a job exactly once (DB-level unique constraint);
  * applications are never deletable by the candidate once submitted, only
    withdrawable — status history stays honest;
  * salary ranges are validated (min ≤ max) and jobs auto-close at deadline.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def unique_slug(model, value, exclude_pk=None) -> str:
    base = slugify(value)[:60] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug


class Company(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="companies")
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=170, unique=True, blank=True, editable=False)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    about = models.TextField(blank=True)
    logo_emoji = models.CharField(max_length=8, default="🏢")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Company, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("company_detail", kwargs={"slug": self.slug})

    @property
    def open_jobs(self) -> int:
        return self.jobs.filter(status=Job.Status.OPEN).count()


class Job(models.Model):
    class Type(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class Level(models.TextChoices):
        JUNIOR = "junior", "Junior"
        MID = "mid", "Mid-level"
        SENIOR = "senior", "Senior"
        LEAD = "lead", "Lead / Principal"

    class Remote(models.TextChoices):
        ONSITE = "onsite", "On-site"
        HYBRID = "hybrid", "Hybrid"
        REMOTE = "remote", "Remote"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="jobs")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs_posted")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=190, unique=True, blank=True, editable=False)
    description = models.TextField()
    requirements = models.TextField(blank=True, help_text="One requirement per line")
    location = models.CharField(max_length=120, default="Remote")
    remote = models.CharField(max_length=8, choices=Remote.choices, default=Remote.REMOTE)
    job_type = models.CharField(max_length=12, choices=Type.choices, default=Type.FULL_TIME)
    level = models.CharField(max_length=8, choices=Level.choices, default=Level.MID)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(Decimal("0"))])
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     validators=[MinValueValidator(Decimal("0"))])
    salary_currency = models.CharField(max_length=8, default="USD")
    tags = models.CharField(max_length=240, blank=True, help_text="Comma-separated skills, e.g. Django, PostgreSQL")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    deadline = models.DateField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["status", "-created"])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Job, self.title, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} @ {self.company.name}"

    def get_absolute_url(self):
        return reverse("job_detail", kwargs={"slug": self.slug})

    def clean(self):
        errors = {}
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            errors["salary_max"] = "Maximum salary must be greater than or equal to the minimum."
        if self.deadline and self.deadline < timezone.localdate():
            errors["deadline"] = "The application deadline cannot be in the past."
        if errors:
            raise ValidationError(errors)

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def requirement_list(self) -> list[str]:
        return [r.strip() for r in self.requirements.splitlines() if r.strip()]

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN and not self.is_expired

    @property
    def is_expired(self) -> bool:
        return bool(self.deadline and self.deadline < timezone.localdate())

    @property
    def days_left(self) -> int | None:
        if not self.deadline:
            return None
        return max((self.deadline - timezone.localdate()).days, 0)

    @property
    def salary_display(self) -> str:
        if self.salary_min is None and self.salary_max is None:
            return "Salary not disclosed"

        def fmt(value) -> str:
            return f"{value:,.0f}"

        if self.salary_min and self.salary_max:
            return f"{self.salary_currency} {fmt(self.salary_min)} – {fmt(self.salary_max)}"
        value = self.salary_min or self.salary_max
        return f"{self.salary_currency} {fmt(value)}+"

    @property
    def application_count(self) -> int:
        return self.applications.count()


class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Under review"
        SHORTLISTED = "shortlisted", "Shortlisted"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer made"
        HIRED = "hired", "Hired"
        REJECTED = "rejected", "Not selected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    BADGE = {
        Status.SUBMITTED: "badge-info", Status.REVIEWING: "badge-info",
        Status.SHORTLISTED: "badge-brand", Status.INTERVIEW: "badge-warn",
        Status.OFFER: "badge-ok", Status.HIRED: "badge-ok",
        Status.REJECTED: "badge-bad", Status.WITHDRAWN: "badge",
    }
    FINAL_STATUSES = (Status.REJECTED, Status.WITHDRAWN)

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    cover_letter = models.TextField(blank=True)
    resume = models.FileField(upload_to="resumes/%Y/%m/", blank=True)
    portfolio_url = models.URLField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SUBMITTED)
    employer_notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "applicant")     # apply exactly once
        ordering = ["-created"]

    def __str__(self):
        return f"{self.applicant.username} → {self.job.title}"

    @property
    def status_badge(self) -> str:
        return self.BADGE.get(self.status, "badge-info")

    @property
    def is_active(self) -> bool:
        return self.status not in self.FINAL_STATUSES

    def withdraw(self):
        if not self.is_active:
            raise ValidationError("This application is already closed.")
        self.status = self.Status.WITHDRAWN
        self.save(update_fields=["status", "updated"])


class SavedJob(models.Model):
    """Bookmarked jobs for a candidate."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_jobs")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "job")
        ordering = ["-created"]

    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"
