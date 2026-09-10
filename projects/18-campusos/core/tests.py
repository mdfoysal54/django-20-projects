"""CampusOS domain tests."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AcademicYear, Book, Exam, FeeHead, Guardian, Invoice, Klass, School, Score,
    Section, Student, Subject, money,
)
from .services import (
    DomainError, attendance_rate, collect_fee, enrol, issue_book, mark_register,
    record_score, return_book,
)


def campus():
    year = AcademicYear.objects.create(name="2026", starts_on="2026-01-01", ends_on="2026-12-31", is_current=True)
    klass = Klass.objects.create(name="Class 6", rank=6)
    section = Section.objects.create(klass=klass, name="A", capacity=2)
    subject = Subject.objects.create(name="Mathematics", code="MATH", klass=klass)
    g = Guardian.objects.create(name="Mrs Karim", phone="0171")
    s1 = Student.objects.create(first_name="Nadia", last_name="Karim", gender="F",
                                born_on="2014-05-01", guardian=g)
    s2 = Student.objects.create(first_name="Rafi", last_name="Islam", gender="M",
                                born_on="2014-08-01", guardian=g)
    s3 = Student.objects.create(first_name="Lina", last_name="Noor", gender="F",
                                born_on="2014-02-01", guardian=g)
    user = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
    return year, klass, section, subject, s1, s2, s3, user


class EnrolmentTests(TestCase):
    def setUp(self):
        self.year, self.klass, self.section, self.subject, self.s1, self.s2, self.s3, self.user = campus()

    def test_capacity_is_enforced(self):
        enrol(self.s1, self.section)
        enrol(self.s2, self.section)
        with self.assertRaises(DomainError):
            enrol(self.s3, self.section)
        self.assertEqual(self.section.students.filter(status=Student.Status.ENROLLED).count(), 2)


class FeeTests(TestCase):
    def setUp(self):
        self.year, self.klass, self.section, self.subject, self.s1, self.s2, self.s3, self.user = campus()
        enrol(self.s1, self.section)
        head = FeeHead.objects.create(name="Tuition", amount=Decimal("5000"))
        self.inv = Invoice.objects.create(student=self.s1, head=head, period="2026-01",
                                          amount=Decimal("5000"), due_on=timezone.localdate())

    def test_partial_then_settle(self):
        collect_fee(self.inv, Decimal("2000"), user=self.user)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invoice.Status.PARTIAL)
        collect_fee(self.inv, Decimal("3000"), user=self.user)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.status, Invoice.Status.PAID)
        self.assertEqual(self.inv.balance, Decimal("0.00"))

    def test_overpayment_refused(self):
        with self.assertRaises(DomainError):
            collect_fee(self.inv, Decimal("9000"))


class AttendanceExamLibraryTests(TestCase):
    def setUp(self):
        self.year, self.klass, self.section, self.subject, self.s1, self.s2, self.s3, self.user = campus()
        enrol(self.s1, self.section)
        enrol(self.s2, self.section)

    def test_attendance_rate_ignores_excused(self):
        day = timezone.localdate()
        mark_register(self.section, day, {self.s1.pk: "P", self.s2.pk: "A"})
        mark_register(self.section, day - timedelta(days=1), {self.s1.pk: "E", self.s2.pk: "P"})
        self.assertEqual(attendance_rate(self.s1), Decimal("100.00"))  # 1 present / 1 countable
        self.assertEqual(attendance_rate(self.s2), Decimal("50.00"))

    def test_grade_boundaries_and_mark_clamp(self):
        exam = Exam.objects.create(name="Mid", year=self.year, held_on=timezone.localdate(), max_marks=100)
        score = record_score(exam, self.s1, self.subject, Decimal("80"))
        self.assertEqual(score.grade, "A+")
        self.assertTrue(score.passed)
        with self.assertRaises(DomainError):
            record_score(exam, self.s1, self.subject, Decimal("140"))

    def test_library_cannot_over_loan(self):
        book = Book.objects.create(title="The Pragmatic Student", isbn="978-1", copies=1)
        issue_book(book, self.s1)
        with self.assertRaises(DomainError):
            issue_book(book, self.s2)
        loan = book.loans.get()
        return_book(loan)
        issue_book(book, self.s2)  # now free
        self.assertEqual(book.loans.filter(returned_on__isnull=True).count(), 1)


class ViewSeederTests(TestCase):
    def test_landing_public(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_dashboard_requires_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_seed_demo(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Student.objects.filter(status=Student.Status.ENROLLED).count(), 4)
        self.assertTrue(Invoice.objects.exists())
        self.assertTrue(Exam.objects.exists())
        self.assertTrue(Book.objects.exists())
        self.assertTrue(User.objects.filter(username="alice").exists())
