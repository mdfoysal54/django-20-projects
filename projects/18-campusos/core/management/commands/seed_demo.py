"""Seed CampusOS with a working Dhaka academy."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    AcademicYear, Attendance, Book, Exam, FeeHead, Guardian, Invoice, Klass,
    Notice, Period, Profile, Route, School, Section, Staff, Student, Subject,
)
from core.services import collect_fee, enrol, issue_book, mark_register, record_score, send_sms


class Command(BaseCommand):
    help = "Seed CampusOS demo academy."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write("Refusing to seed with DEBUG=False.")
            return
        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@campusos.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()
        alice, created = User.objects.get_or_create(username="alice",
                                                    defaults={"first_name": "Alice", "last_name": "Rahman",
                                                              "email": "alice@campusos.dev"})
        if created:
            alice.set_password("DemoPass123!")
            alice.save()
        Profile.objects.get_or_create(user=admin, defaults={"role": Profile.Role.ADMIN})
        Profile.objects.get_or_create(user=alice, defaults={"role": Profile.Role.TEACHER})

        school = School.get()
        school.name = "Northfield Academy"
        school.motto = "Learn with honour."
        school.save()

        year, _ = AcademicYear.objects.get_or_create(name="2026",
                                                     defaults={"starts_on": "2026-01-01", "ends_on": "2026-12-31",
                                                               "is_current": True})
        klass, _ = Klass.objects.get_or_create(name="Class 6", defaults={"rank": 6})
        sec_a, _ = Section.objects.get_or_create(klass=klass, name="A", defaults={"capacity": 40})
        sec_b, _ = Section.objects.get_or_create(klass=klass, name="B", defaults={"capacity": 40})
        math, _ = Subject.objects.get_or_create(code="MATH", defaults={"name": "Mathematics", "klass": klass})
        eng, _ = Subject.objects.get_or_create(code="ENG", defaults={"name": "English", "klass": klass})
        sci, _ = Subject.objects.get_or_create(code="SCI", defaults={"name": "Science", "klass": klass})

        staff, _ = Staff.objects.get_or_create(user=alice, defaults={"code": "T-01", "designation": "Class teacher"})
        staff.subjects.set([math, eng])

        g1, _ = Guardian.objects.get_or_create(phone="01720000001", defaults={"name": "Mrs Karim"})
        g2, _ = Guardian.objects.get_or_create(phone="01720000002", defaults={"name": "Mr Islam"})
        names = [("Nadia", "Karim", "F", g1, sec_a), ("Rafi", "Islam", "M", g2, sec_a),
                 ("Lina", "Noor", "F", g1, sec_a), ("Omar", "Hasan", "M", g2, sec_b),
                 ("Sara", "Ahmed", "F", g1, sec_b), ("Ibrahim", "Khan", "M", g2, sec_b)]
        students = []
        for first, last, gender, g, sec in names:
            st, _ = Student.objects.get_or_create(first_name=first, last_name=last,
                                                  defaults={"gender": gender, "born_on": "2014-06-01", "guardian": g})
            if st.status != Student.Status.ENROLLED:
                enrol(st, sec)
            students.append(st)
        applicant, _ = Student.objects.get_or_create(first_name="Pending", last_name="Applicant",
                                                     defaults={"gender": "F", "born_on": "2015-01-01", "guardian": g1,
                                                               "status": Student.Status.APPLICANT})

        tuition, _ = FeeHead.objects.get_or_create(name="Tuition", defaults={"amount": Decimal("6500")})
        lab, _ = FeeHead.objects.get_or_create(name="Lab", defaults={"amount": Decimal("1500")})
        if not Invoice.objects.exists():
            for st in students[:4]:
                inv = Invoice.objects.create(student=st, head=tuition, period="2026-01",
                                             amount=tuition.amount, due_on=timezone.localdate() + timedelta(days=7))
                if st.first_name == "Nadia":
                    collect_fee(inv, Decimal("6500"), "bkash", alice)
                elif st.first_name == "Rafi":
                    collect_fee(inv, Decimal("2000"), "cash", alice)

        exam, _ = Exam.objects.get_or_create(name="First term", year=year,
                                             defaults={"held_on": timezone.localdate() - timedelta(days=10)})
        if not exam.scores.exists():
            record_score(exam, students[0], math, Decimal("88"))
            record_score(exam, students[0], eng, Decimal("74"))
            record_score(exam, students[1], math, Decimal("51"))
            record_score(exam, students[1], sci, Decimal("39"))

        today = timezone.localdate()
        mark_register(sec_a, today, {students[0].pk: "P", students[1].pk: "L", students[2].pk: "A"})
        mark_register(sec_a, today - timedelta(days=1), {students[0].pk: "P", students[1].pk: "P", students[2].pk: "E"})

        if not Period.objects.exists():
            Period.objects.create(weekday=0, slot=1, starts="08:00", ends="08:45",
                                  section=sec_a, subject=math, teacher=staff)
            Period.objects.create(weekday=0, slot=2, starts="08:50", ends="09:35",
                                  section=sec_a, subject=eng, teacher=staff)

        book, _ = Book.objects.get_or_create(isbn="978-984-01",
                                             defaults={"title": "The Pragmatic Student", "author": "Hunt", "copies": 3})
        if not book.loans.exists():
            issue_book(book, students[0])
        Route.objects.get_or_create(name="Gulshan loop", defaults={"vehicle": "Dhaka-Metro-12", "fee": Decimal("1500")})
        Notice.objects.get_or_create(title="Sports day", defaults={"body": "Friday, field at 9am.", "author": alice})
        send_sms(g1.phone, "Northfield: Nadia's tuition is settled. Thank you.")

        self.stdout.write(self.style.SUCCESS(
            f"CampusOS seeded: {Student.objects.count()} students, {Invoice.objects.count()} invoices, "
            f"{Exam.objects.count()} exams."
        ))
