"""Seed AttendX with teachers, cohorts, students and a few weeks of registers."""
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import AttendanceRecord, Cohort, Enrollment, Session

TEACHERS = [("teacher_ayesha", "Ayesha", "Rahman"), ("teacher_imran", "Imran", "Chowdhury")]
COHORTS = [
    ("teacher_ayesha", "CS-101 — Intro to Programming", "Computer Science", "Lab 3", "Sun & Tue, 10:00–11:30",
     "Variables, control flow, functions and a first project."),
    ("teacher_ayesha", "CS-220 — Databases", "Computer Science", "Room 210", "Mon & Wed, 14:00–15:30",
     "Relational modelling, SQL, indexes and transactions."),
    ("teacher_imran", "ENG-140 — Technical Writing", "English", "Room 108", "Tue & Thu, 09:00–10:30",
     "Documentation, proposals and writing for engineers."),
]
STUDENTS = ["nadia", "rakib", "marufa", "sabbir", "tanvir", "farhana", "jamil", "sumaiya"]
TOPICS = [
    "Variables and types", "Control flow", "Functions and scope", "Collections deep dive",
    "Error handling", "Testing your code", "Interfaces and contracts", "Project workshop",
    "Performance basics", "Review and exam prep",
]


class Command(BaseCommand):
    help = "Create demo teachers, cohorts, students and attendance history."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        rng = random.Random(1409)
        today = timezone.localdate()

        for username, first, last in TEACHERS:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"first_name": first, "last_name": last,
                                                                 "email": f"{username}@attendx.dev"})
            if created:
                user.set_password("DemoPass123!")
                user.save()

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@attendx.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        for username in STUDENTS:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"email": f"{username}@student.attendx.dev"})
            if created:
                user.set_password("DemoPass123!")
                user.save()

        for teacher_name, name, subject, room, note, description in COHORTS:
            teacher = User.objects.get(username=teacher_name)
            cohort, created = Cohort.objects.get_or_create(
                teacher=teacher, name=name,
                defaults={"subject": subject, "room": room, "meeting_note": note, "description": description})
            if not created:
                continue

            enrolled = rng.sample(STUDENTS, k=6)
            for username in enrolled:
                Enrollment.objects.create(cohort=cohort, student=User.objects.get(username=username))

            # Ten past sessions: nine held with registers, one cancelled.
            for i in range(10):
                days_ago = (10 - i) * 3
                session = Session.objects.create(
                    cohort=cohort, date=today - timedelta(days=days_ago),
                    topic=TOPICS[i % len(TOPICS)],
                    status=Session.Status.CANCELLED if i == 6 else Session.Status.HELD,
                    note="Guest speaker cancelled." if i == 6 else "",
                )
                if session.status != Session.Status.HELD:
                    continue
                for username in enrolled:
                    # Most students attend most of the time; one has a wobble.
                    roll = rng.random()
                    if username == "sabbir":
                        status = AttendanceRecord.Status.PRESENT if roll > 0.45 else (
                            AttendanceRecord.Status.LATE if roll > 0.3 else AttendanceRecord.Status.ABSENT)
                    else:
                        status = (AttendanceRecord.Status.PRESENT if roll > 0.2 else
                                  AttendanceRecord.Status.LATE if roll > 0.1 else
                                  AttendanceRecord.Status.ABSENT if roll > 0.05 else
                                  AttendanceRecord.Status.EXCUSED)
                    session.mark(User.objects.get(username=username), status,
                                 marked_by=teacher)

            # An upcoming session with no register yet, plus today's register in progress.
            Session.objects.create(cohort=cohort, date=today + timedelta(days=2),
                                   topic="Next up: " + TOPICS[len(enrolled) % len(TOPICS)],
                                   status=Session.Status.SCHEDULED)
            today_session = Session.objects.create(cohort=cohort, date=today,
                                                   topic="Today's workshop", status=Session.Status.HELD)
            for username in enrolled[:3]:
                today_session.mark(User.objects.get(username=username), AttendanceRecord.Status.PRESENT,
                                   marked_by=teacher)

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Cohort.objects.count()} cohorts, {Session.objects.count()} sessions, "
            f"{Enrollment.objects.count()} enrolments, {AttendanceRecord.objects.count()} attendance records."
        ))
