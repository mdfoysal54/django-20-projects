"""HelpDesk models — support tickets, conversation threads and SLA tracking."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    emoji = models.CharField(max_length=8, default="🎧")
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting on customer"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    #: First-response SLA per priority (hours) — used to compute the deadline.
    SLA_HOURS = {Priority.URGENT: 4, Priority.HIGH: 8, Priority.NORMAL: 24, Priority.LOW: 72}

    #: Which statuses an agent may move a ticket to from each state.
    ALLOWED_TRANSITIONS = {
        Status.OPEN: {Status.IN_PROGRESS, Status.WAITING, Status.RESOLVED, Status.CLOSED},
        Status.IN_PROGRESS: {Status.WAITING, Status.RESOLVED, Status.CLOSED, Status.OPEN},
        Status.WAITING: {Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED, Status.OPEN},
        Status.RESOLVED: {Status.CLOSED, Status.OPEN, Status.IN_PROGRESS},
        Status.CLOSED: {Status.OPEN, Status.IN_PROGRESS},
    }

    reference = models.CharField(max_length=12, unique=True, editable=False)
    subject = models.CharField(max_length=160)
    body = models.TextField(help_text="What's going wrong? Include anything you've already tried.")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="tickets")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tickets")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="assigned_tickets")
    priority = models.CharField(max_length=7, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=11, choices=Status.choices, default=Status.OPEN)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    sla_due = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["status", "priority"]),
                   models.Index(fields=["assignee", "status"])]

    def __str__(self):
        return f"{self.reference} — {self.subject}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._new_reference()
        if self.sla_due is None:
            self.sla_due = timezone.now() + timedelta(hours=self.SLA_HOURS[self.priority])
        super().save(*args, **kwargs)

    @staticmethod
    def _new_reference() -> str:
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        while True:
            ref = "HD-" + "".join(secrets.choice(alphabet) for _ in range(6))
            if not Ticket.objects.filter(reference=ref).exists():
                return ref

    def get_absolute_url(self):
        return reverse("ticket_detail", kwargs={"reference": self.reference})

    # ------------------------------------------------------------------ state
    @property
    def is_open(self) -> bool:
        return self.status not in {self.Status.RESOLVED, self.Status.CLOSED}

    @property
    def is_breached(self) -> bool:
        """SLA breached: no agent reply before the deadline (or still waiting past it)."""
        if self.first_response_at:
            return self.first_response_at > self.sla_due
        return timezone.now() > self.sla_due

    @property
    def minutes_to_first_response(self):
        if not self.first_response_at:
            return None
        return round((self.first_response_at - self.created).total_seconds() / 60)

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    # ------------------------------------------------------------- domain ops
    def add_message(self, author, body, internal=False):
        """Append a reply or internal note; records the first public agent response."""
        message = TicketMessage.objects.create(ticket=self, author=author, body=body, internal=internal)
        if not internal and author == self.assignee and self.first_response_at is None:
            self.first_response_at = timezone.now()
            self.save(update_fields=["first_response_at"])
        elif not internal and author != self.requester and self.first_response_at is None:
            # Any agent reply counts as a first response, assigned or not.
            self.first_response_at = timezone.now()
            self.save(update_fields=["first_response_at"])
        Ticket.objects.filter(pk=self.pk).update(updated=timezone.now())
        return message

    def assign_to(self, agent):
        """Agents only. Assigning an unclaimed ticket moves it into progress."""
        fields = ["assignee", "updated"]
        self.assignee = agent
        if self.status == self.Status.OPEN:
            self.status = self.Status.IN_PROGRESS
            fields.append("status")
        self.updated = timezone.now()
        self.save(update_fields=fields)
        TicketEvent.objects.create(ticket=self, actor=agent, kind="assigned",
                                   detail=f"Assigned to {agent.username}")

    def set_priority(self, priority, actor):
        """Priority changes recompute the SLA deadline from today (not from creation)."""
        if priority not in dict(self.Priority.choices):
            raise ValueError("Unknown priority")
        self.priority = priority
        self.sla_due = timezone.now() + timedelta(hours=self.SLA_HOURS[priority])
        self.save(update_fields=["priority", "sla_due"])
        TicketEvent.objects.create(ticket=self, actor=actor, kind="priority",
                                   detail=f"Priority set to {self.get_priority_display()}")

    @transaction.atomic
    def set_status(self, new_status, actor):
        """Guarded status machine — illegal jumps raise ValueError."""
        if new_status not in dict(self.Status.choices):
            raise ValueError("Unknown status")
        if new_status == self.status:
            return self
        if not self.can_transition_to(new_status):
            raise ValueError(f"Cannot move a {self.get_status_display()} ticket "
                             f"to {dict(self.Status.choices)[new_status]}.")
        old = self.status
        self.status = new_status
        fields = ["status", "updated"]
        self.updated = timezone.now()
        if new_status == self.Status.RESOLVED and self.resolved_at is None:
            self.resolved_at = timezone.now()
            fields.append("resolved_at")
        if new_status in {self.Status.OPEN, self.Status.IN_PROGRESS}:
            self.resolved_at = None
            fields.append("resolved_at")
        self.save(update_fields=fields)
        TicketEvent.objects.create(ticket=self, actor=actor, kind="status",
                                   detail=f"{old} → {new_status}")
        return self


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ticket_messages")
    body = models.TextField(max_length=4000)
    internal = models.BooleanField(default=False, help_text="Internal notes are visible to agents only.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self):
        return f"{'note' if self.internal else 'reply'} by {self.author.username}"


class TicketEvent(models.Model):
    """Immutable audit trail of the ticket's life."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="ticket_events")
    kind = models.CharField(max_length=20)
    detail = models.CharField(max_length=200)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self):
        return f"{self.kind}: {self.detail}"


class Feedback(models.Model):
    """One satisfaction score per resolved ticket."""

    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name="feedback")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    comment = models.CharField(max_length=300, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(score__gte=1) & models.Q(score__lte=5), name="feedback_score_1_5"),
        ]

    def __str__(self):
        return f"{self.ticket.reference}: {self.score}/5"
