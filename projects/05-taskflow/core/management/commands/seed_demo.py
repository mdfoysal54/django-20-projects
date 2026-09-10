"""Seed TaskFlow with a realistic multi-project workspace."""
from datetime import timedelta
from random import Random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Activity, Comment, Membership, Project, Task

rng = Random(42)  # deterministic demo data

PROJECTS = [
    {
        "name": "Website Redesign", "color": "#4f46e5", "owner": "alice",
        "description": "Marketing site rebuild: new design system, faster pages, better SEO.",
        "members": [("bob", Membership.Role.MEMBER), ("carol", Membership.Role.ADMIN),
                    ("dave", Membership.Role.VIEWER)],
        "tasks": [
            ("Audit current pages and pick the URL map", Task.Status.DONE, Task.Priority.HIGH, "carol", -9, 6),
            ("Design tokens: colour, spacing, type scale", Task.Status.DONE, Task.Priority.MEDIUM, "bob", -5, 8),
            ("Build the new homepage hero section", Task.Status.IN_PROGRESS, Task.Priority.HIGH, "alice", 2, 10),
            ("Responsive audit — tablet breakpoints", Task.Status.TODO, Task.Priority.MEDIUM, "bob", 5, 6),
            ("Accessibility pass: focus states + contrast", Task.Status.REVIEW, Task.Priority.URGENT, "carol", 1, 8),
            ("Set up analytics events for CTAs", Task.Status.BACKLOG, Task.Priority.LOW, None, 14, 4),
            ("Write launch-day checklist", Task.Status.TODO, Task.Priority.LOW, "dave", 12, 3),
        ],
    },
    {
        "name": "Mobile App v2", "color": "#0ea5e9", "owner": "bob",
        "description": "Offline mode, push notifications and a redesigned onboarding flow.",
        "members": [("alice", Membership.Role.MEMBER), ("dave", Membership.Role.MEMBER)],
        "tasks": [
            ("Spike: local storage strategy (SQLite vs Realm)", Task.Status.DONE, Task.Priority.HIGH, "bob", -11, 12),
            ("Offline sync queue with retry/backoff", Task.Status.IN_PROGRESS, Task.Priority.URGENT, "bob", 3, 16),
            ("Push notification permission flow", Task.Status.TODO, Task.Priority.HIGH, "alice", 6, 8),
            ("Onboarding screens 1–3 implementation", Task.Status.IN_PROGRESS, Task.Priority.MEDIUM, "dave", 4, 10),
            ("Beta feedback triage", Task.Status.BACKLOG, Task.Priority.LOW, None, 20, 4),
            ("Battery usage profiling", Task.Status.REVIEW, Task.Priority.MEDIUM, "bob", 2, 6),
        ],
    },
    {
        "name": "Q3 Security Hardening", "color": "#dc2626", "owner": "carol",
        "description": "Dependency upgrades, CSP rollout and the incident runbook update.",
        "members": [("alice", Membership.Role.ADMIN), ("bob", Membership.Role.VIEWER)],
        "tasks": [
            ("Inventory all direct dependencies", Task.Status.DONE, Task.Priority.HIGH, "carol", -6, 8),
            ("Upgrade framework to latest LTS", Task.Status.DONE, Task.Priority.URGENT, "carol", -2, 10),
            ("Roll out CSP report-only for 1 week", Task.Status.IN_PROGRESS, Task.Priority.HIGH, "alice", 1, 6),
            ("Rotate all service credentials", Task.Status.TODO, Task.Priority.URGENT, "alice", 3, 4),
            ("Incident runbook: tabletop exercise", Task.Status.TODO, Task.Priority.MEDIUM, None, 9, 6),
            ("Pen-test findings review", Task.Status.BACKLOG, Task.Priority.HIGH, "carol", 15, 5),
        ],
    },
]

COMMENTS = [
    "Pushed a first pass — feedback welcome, especially on spacing.",
    "Blocked on the API contract; syncing with the platform team tomorrow.",
    "Nice, this is much faster now. Rebased on main and merged.",
    "Left two small notes inline, nothing blocking.",
    "Moved the deadline to Friday — plenty of runway.",
]


class Command(BaseCommand):
    help = "Create demo users, projects, memberships, tasks, comments and activity."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        people = {}
        for username, staff in [("alice", False), ("bob", False), ("carol", False),
                                ("dave", False), ("admin", True)]:
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@taskflow.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = user.is_superuser = True
            user.save()
            people[username] = user

        today = timezone.localdate()
        for spec in PROJECTS:
            owner = people[spec["owner"]]
            project, created = Project.objects.get_or_create(
                name=spec["name"],
                defaults={"owner": owner, "description": spec["description"], "color": spec["color"]},
            )
            for username, role in spec["members"]:
                Membership.objects.get_or_create(
                    project=project, user=people[username], defaults={"role": role},
                )
            if not created:
                continue
            Activity.log(project, owner, f"created the project “{project.name}”")
            for position, (title, status, priority, assignee_name, due_offset, estimate) in enumerate(
                    spec["tasks"], start=1):
                assignee = people[assignee_name] if assignee_name else None
                task = Task.objects.create(
                    project=project,
                    title=title, status=status, priority=priority,
                    assignee=assignee, created_by=owner, position=position,
                    estimate_hours=estimate,
                    due_date=today + timedelta(days=due_offset),
                    description=f"{title}. Owner: {assignee_name or 'unassigned'}.",
                    completed_at=timezone.now() if status == Task.Status.DONE else None,
                )
                Activity.log(project, owner, f"created task “{task.title}”", task=task)
                if rng.random() > 0.55:
                    Comment.objects.create(
                        task=task, author=people[rng.choice(["alice", "bob", "carol"])],
                        body=rng.choice(COMMENTS),
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Project.objects.count()} projects, {Task.objects.count()} tasks, "
            f"{Membership.objects.count()} memberships, {Comment.objects.count()} comments."
        ))
