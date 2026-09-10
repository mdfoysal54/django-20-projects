"""TaskFlow data models — projects, memberships, tasks, comments, activity.

Permission model (enforced in views, expressible here):
  * Project.owner  — full control (edit project, manage members, delete tasks)
  * Membership(role=admin)   — same as owner except ownership transfer
  * Membership(role=member)  — create/edit tasks, comment, move tasks
  * Membership(role=viewer)  — read-only
A user only ever touches projects they are a member of; queries are always
filtered through memberships (see core/access.py).
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def unique_slug(model, value, exclude_pk=None) -> str:
    base = slugify(value)[:50] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug


class Project(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects")
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True, editable=False)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default="#4f46e5", help_text="Hex accent colour, e.g. #4f46e5")
    archived = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Project, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("project_detail", kwargs={"slug": self.slug})

    def role_of(self, user):
        """Return 'owner' | 'admin' | 'member' | 'viewer' | None for a user."""
        if not user or not user.is_authenticated:
            return None
        if self.owner_id == user.id:
            return "owner"
        membership = self.memberships.filter(user=user).first()
        return membership.role if membership else None

    def can_edit(self, user) -> bool:
        return self.role_of(user) in ("owner", "admin", "member")

    def can_manage(self, user) -> bool:
        return self.role_of(user) in ("owner", "admin")

    def can_view(self, user) -> bool:
        return self.role_of(user) is not None

    @property
    def task_count(self) -> int:
        return self.tasks.count()

    @property
    def done_count(self) -> int:
        return self.tasks.filter(status=Task.Status.DONE).count()

    @property
    def progress_percent(self) -> int:
        total = self.task_count
        return round(self.done_count * 100 / total) if total else 0

    @property
    def member_count(self) -> int:
        return self.memberships.count() + 1  # + owner


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=8, choices=Role.choices, default=Role.MEMBER)
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("project", "user")

    def __str__(self):
        return f"{self.user.username} · {self.project.name} ({self.role})"

    def clean(self):
        if self.project_id and self.user_id and self.project.owner_id == self.user_id:
            raise ValidationError("The project owner is already a member by definition.")


class Task(models.Model):
    class Status(models.TextChoices):
        BACKLOG = "backlog", "Backlog"
        TODO = "todo", "To do"
        IN_PROGRESS = "progress", "In progress"
        REVIEW = "review", "Review"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    PRIORITY_BADGE = {Priority.LOW: "badge", Priority.MEDIUM: "badge-info",
                      Priority.HIGH: "badge-warn", Priority.URGENT: "badge-bad"}
    BOARD_COLUMNS = [Status.BACKLOG, Status.TODO, Status.IN_PROGRESS, Status.REVIEW, Status.DONE]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.MEDIUM)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_tasks")
    due_date = models.DateField(null=True, blank=True)
    estimate_hours = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    position = models.PositiveIntegerField(default=0, help_text="Ordering inside its column")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "-priority", "-created"]
        indexes = [models.Index(fields=["project", "status", "position"])]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("task_detail", kwargs={"pk": self.pk})

    @property
    def priority_badge(self) -> str:
        return self.PRIORITY_BADGE.get(self.priority, "badge")

    @property
    def is_overdue(self) -> bool:
        return bool(self.due_date and self.status != self.Status.DONE and self.due_date < timezone.localdate())

    @property
    def due_state(self) -> str:
        """'overdue' | 'today' | 'soon' | 'later' | '' — for badges in templates."""
        if not self.due_date or self.status == self.Status.DONE:
            return ""
        delta = (self.due_date - timezone.localdate()).days
        if delta < 0:
            return "overdue"
        if delta == 0:
            return "today"
        if delta <= 3:
            return "soon"
        return "later"

    def set_status(self, new_status: str, by_user=None):
        """Move a task between columns, maintaining completed_at."""
        if new_status not in self.Status.values:
            raise ValidationError("Unknown status.")
        self.status = new_status
        self.completed_at = timezone.now() if new_status == self.Status.DONE else None
        self.save(update_fields=["status", "completed_at", "updated"])
        if by_user is not None:
            Activity.objects.create(
                project=self.project, user=by_user, task=self,
                verb=f"moved “{self.title}” to {self.get_status_display()}",
            )


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_comments")
    body = models.TextField(max_length=2000)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.task.title}"


class Activity(models.Model):
    """Lightweight append-only audit/feed entries."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="activities")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    verb = models.CharField(max_length=240)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name_plural = "Activities"

    def __str__(self):
        return f"{self.user.username} {self.verb}"

    @classmethod
    def log(cls, project, user, verb, task=None):
        return cls.objects.create(project=project, user=user, verb=verb, task=task)
