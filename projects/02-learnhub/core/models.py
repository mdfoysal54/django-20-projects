"""LearnHub data models — courses, lessons, enrolments and progress."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from .models_utils import unique_slug


class Course(models.Model):
    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    LEVEL_BADGE = {Level.BEGINNER: "badge-ok", Level.INTERMEDIATE: "badge-warn", Level.ADVANCED: "badge-bad"}

    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="courses_taught")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=190, unique=True, blank=True, editable=False)
    summary = models.CharField(max_length=240, blank=True, help_text="One line shown on cards")
    description = models.TextField(blank=True)
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.BEGINNER)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Course, self.title, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("course_detail", kwargs={"slug": self.slug})

    @property
    def published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def is_free(self) -> bool:
        return self.price == 0

    @property
    def lessons(self):
        return self.lesson_set.order_by("order", "pk")

    @property
    def lesson_count(self) -> int:
        return self.lesson_set.count()

    @property
    def total_minutes(self) -> int:
        return self.lesson_set.aggregate(total=models.Sum("duration_minutes"))["total"] or 0

    @property
    def student_count(self) -> int:
        return self.enrollments.count()

    @property
    def level_badge(self) -> str:
        return self.LEVEL_BADGE.get(self.level, "badge-info")


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    order = models.PositiveIntegerField(default=1, help_text="Position in the curriculum")
    content = models.TextField(help_text="Lesson body (plain text / light markdown)")
    duration_minutes = models.PositiveIntegerField(default=10, validators=[MaxValueValidator(600)])
    # Optional embed for exercise links (kept as plain URL — validated on forms)
    resource_url = models.URLField(blank=True)

    class Meta:
        ordering = ["order", "pk"]
        unique_together = ("course", "order")

    def __str__(self):
        return f"{self.course.title} · {self.order}. {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-enrolled_at"]

    def __str__(self):
        return f"{self.student.username} → {self.course.title}"

    @property
    def completed_lessons(self) -> int:
        return self.progress.filter(completed=True).count()

    @property
    def progress_percent(self) -> int:
        total = self.course.lesson_count
        if total == 0:
            return 0
        return round(self.completed_lessons * 100 / total)

    @property
    def is_finished(self) -> bool:
        return self.course.lesson_count > 0 and self.completed_lessons == self.course.lesson_count


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress_records")
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("enrollment", "lesson")
        verbose_name_plural = "Lesson progress"

    def __str__(self):
        state = "done" if self.completed else "in progress"
        return f"{self.enrollment.student.username} · {self.lesson.title} ({state})"
