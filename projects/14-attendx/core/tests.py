"""AttendX domain tests — register rules, rate maths, roster privacy."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AttendanceRecord, Cohort, Enrollment, Session, rate_band, student_report


def make_cohort(teacher, name="CS-101", students=("s1", "s2", "s3")):
    cohort = Cohort.objects.create(teacher=teacher, name=name, subject="Computer Science", room="Lab 3")
    for username in students:
        student, _ = User.objects.get_or_create(username=username, defaults={"password": "x"})
        Enrollment.objects.create(cohort=cohort, student=student)
    return cohort


def make_session(cohort, days_ago=1, status=Session.Status.HELD, topic="Recursion"):
    return Session.objects.create(cohort=cohort, date=timezone.localdate() - timedelta(days=days_ago),
                                  topic=topic, status=status)


class RegisterRulesTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher)
        self.session = make_session(self.cohort)

    def test_marking_records_attendance(self):
        student = User.objects.get(username="s1")
        record = self.session.mark(student, AttendanceRecord.Status.LATE, marked_by=self.teacher)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertEqual(record.marked_by, self.teacher)
        self.assertEqual(self.session.records.count(), 1)

    def test_marking_twice_updates_the_same_record(self):
        student = User.objects.get(username="s1")
        self.session.mark(student, AttendanceRecord.Status.ABSENT, marked_by=self.teacher)
        self.session.mark(student, AttendanceRecord.Status.PRESENT, marked_by=self.teacher)
        self.assertEqual(self.session.records.filter(student=student).count(), 1)
        self.assertEqual(self.session.records.get(student=student).status, AttendanceRecord.Status.PRESENT)

    def test_database_refuses_duplicate_records(self):
        student = User.objects.get(username="s1")
        AttendanceRecord.objects.create(session=self.session, student=student, status="present")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttendanceRecord.objects.create(session=self.session, student=student, status="absent")

    def test_cannot_mark_a_student_who_is_not_enrolled(self):
        outsider = User.objects.create_user("outsider", password="Str0ng!Passw0rd")
        with self.assertRaises(ValueError):
            self.session.mark(outsider, AttendanceRecord.Status.PRESENT, marked_by=self.teacher)

    def test_mark_all_present_then_adjust(self):
        self.session.mark_all_present(marked_by=self.teacher)
        self.assertEqual(self.session.records.count(), 3)
        self.assertTrue(all(r.status == AttendanceRecord.Status.PRESENT for r in self.session.records.all()))

    def test_unknown_status_raises(self):
        with self.assertRaises(ValueError):
            self.session.mark(User.objects.get(username="s1"), "banana", marked_by=self.teacher)

    def test_records_are_removed_with_the_session(self):
        self.session.mark(User.objects.get(username="s1"), AttendanceRecord.Status.PRESENT)
        self.session.delete()
        self.assertEqual(AttendanceRecord.objects.count(), 0)


class StatusAndTimingRulesTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher)

    def test_future_session_cannot_be_marked(self):
        future = make_session(self.cohort, days_ago=-2, status=Session.Status.HELD, topic="Next week")
        self.assertTrue(future.is_future)
        self.assertFalse(future.can_mark())

    def test_scheduled_session_cannot_be_marked(self):
        scheduled = make_session(self.cohort, days_ago=1, status=Session.Status.SCHEDULED, topic="Planned")
        self.assertFalse(scheduled.can_mark())

    def test_held_past_session_can_be_marked(self):
        self.assertTrue(make_session(self.cohort, topic="Held").can_mark())

    def test_take_attendance_view_refuses_a_future_session(self):
        future = make_session(self.cohort, days_ago=-1, status=Session.Status.HELD, topic="Tomorrow")
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("take_attendance", kwargs={"pk": future.pk}), follow=True)
        self.assertContains(response, "only take attendance for a session that has been held")


class RateMathsTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher, students=("a", "b"))
        self.sessions = [make_session(self.cohort, days_ago=i + 1, topic=f"Session {i}") for i in range(5)]

    def test_late_counts_as_attended(self):
        student = User.objects.get(username="a")
        for session in self.sessions[:4]:
            session.mark(student, AttendanceRecord.Status.PRESENT)
        self.sessions[4].mark(student, AttendanceRecord.Status.LATE)
        row = [r for r in self.cohort.attendance_summary()["rows"] if r["student"] == student][0]
        self.assertEqual(row["present"], 4)
        self.assertEqual(row["late"], 1)
        self.assertEqual(row["rate"], 100)

    def test_excused_is_removed_from_the_denominator(self):
        student = User.objects.get(username="a")
        self.sessions[0].mark(student, AttendanceRecord.Status.EXCUSED)
        for session in self.sessions[1:]:
            session.mark(student, AttendanceRecord.Status.ABSENT)
        row = [r for r in self.cohort.attendance_summary()["rows"] if r["student"] == student][0]
        self.assertEqual(row["excused"], 1)
        self.assertEqual(row["rate"], 0)                 # 0 of 4 counted sessions

    def test_unmarked_sessions_lower_nobody_but_show_as_unmarked(self):
        summary = self.cohort.attendance_summary()
        self.assertEqual(summary["total_sessions"], 5)
        for row in summary["rows"]:
            self.assertEqual(row["rate"], 0 if row["present"] == 0 and row["late"] == 0 else row["rate"])
            self.assertEqual(row["unmarked"], 5)

    def test_student_report_aggregates_across_cohorts(self):
        student = User.objects.get(username="a")
        cohort2 = Cohort.objects.create(teacher=self.teacher, name="CS-102")
        Enrollment.objects.create(cohort=cohort2, student=student)
        extra = make_session(cohort2, days_ago=2, topic="Second cohort")
        for session in self.sessions:
            session.mark(student, AttendanceRecord.Status.PRESENT)
        extra.mark(student, AttendanceRecord.Status.ABSENT)
        report = student_report(student)
        self.assertEqual(len(report["rows"]), 2)
        self.assertEqual(report["total_counted"], 6)
        self.assertEqual(report["total_attended"], 5)
        self.assertEqual(report["overall_rate"], 83)

    def test_rate_bands(self):
        self.assertEqual(rate_band(None), "none")
        self.assertEqual(rate_band(90), "ok")
        self.assertEqual(rate_band(75), "warn")
        self.assertEqual(rate_band(40), "danger")


class AccessControlTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.rival = User.objects.create_user("rival", password="Str0ng!Passw0rd")
        self.student = User.objects.create_user("s1", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher, students=("s1", "s2"))
        self.session = make_session(self.cohort)

    def test_only_the_teacher_can_open_the_register(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("take_attendance", kwargs={"pk": self.session.pk}))
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.rival)
        self.assertEqual(self.client.get(reverse("take_attendance", kwargs={"pk": self.session.pk})).status_code, 404)

    def test_rival_cannot_post_a_register_either(self):
        self.client.force_login(self.rival)
        response = self.client.post(reverse("take_attendance", kwargs={"pk": self.session.pk}),
                                    {"student_1": "present"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.session.records.count(), 0)

    def test_rival_cannot_view_the_cohort_or_its_report(self):
        self.client.force_login(self.rival)
        self.assertEqual(self.client.get(self.cohort.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("report", kwargs={"pk": self.cohort.pk})).status_code, 404)

    def test_enrolled_student_can_view_the_cohort_but_not_others(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.cohort.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(reverse("report", kwargs={"pk": self.cohort.pk})).status_code, 404)

    def test_student_report_only_contains_own_rows(self):
        other = User.objects.get(username="s2")
        self.session.mark(self.student, AttendanceRecord.Status.PRESENT)
        self.session.mark(other, AttendanceRecord.Status.ABSENT)
        self.client.force_login(self.student)
        response = self.client.get(reverse("my_attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "s2")

    def test_student_cannot_unenrol_a_classmate(self):
        self.client.force_login(self.student)
        response = self.client.post(reverse("cohort_remove_student", kwargs={"pk": self.cohort.pk}),
                                    {"student": User.objects.get(username="s2").pk})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Enrollment.objects.get(cohort=self.cohort, student__username="s2").active)


class JoinAndRosterTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher, students=())
        self.newcomer = User.objects.create_user("newcomer", password="Str0ng!Passw0rd")

    def test_join_with_the_right_code(self):
        self.client.force_login(self.newcomer)
        self.client.post(reverse("cohort_join"), {"code": self.cohort.code.lower()})   # case-insensitive
        self.assertTrue(self.cohort.is_enrolled(self.newcomer))

    def test_wrong_code_enrols_nobody(self):
        self.client.force_login(self.newcomer)
        response = self.client.post(reverse("cohort_join"), {"code": "ZZZZZZ"}, follow=True)
        self.assertContains(response, "No cohort matches that code")
        self.assertFalse(self.cohort.is_enrolled(self.newcomer))

    def test_joining_twice_says_so_and_does_not_duplicate(self):
        self.client.force_login(self.newcomer)
        self.client.post(reverse("cohort_join"), {"code": self.cohort.code})
        response = self.client.post(reverse("cohort_join"), {"code": self.cohort.code}, follow=True)
        self.assertContains(response, "already enrolled")
        self.assertEqual(Enrollment.objects.filter(cohort=self.cohort, student=self.newcomer).count(), 1)

    def test_teacher_is_not_enrolled_in_their_own_cohort(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse("cohort_join"), {"code": self.cohort.code}, follow=True)
        self.assertContains(response, "You teach this cohort")
        self.assertFalse(self.cohort.is_enrolled(self.teacher))

    def test_removing_a_student_keeps_history(self):
        student = User.objects.create_user("leaver", password="Str0ng!Passw0rd")
        Enrollment.objects.create(cohort=self.cohort, student=student)
        session = make_session(self.cohort, topic="Old session")
        session.mark(student, AttendanceRecord.Status.PRESENT)
        self.client.force_login(self.teacher)
        self.client.post(reverse("cohort_remove_student", kwargs={"pk": self.cohort.pk}),
                         {"student": student.pk})
        self.assertFalse(Enrollment.objects.get(cohort=self.cohort, student=student).active)
        self.assertEqual(session.records.count(), 1)     # audit trail survives

    def test_cohort_names_unique_per_teacher(self):
        Cohort.objects.create(teacher=self.teacher, name="English-9")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cohort.objects.create(teacher=self.teacher, name="English-9")


class RegisterViewTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.cohort = make_cohort(self.teacher, students=("s1", "s2"))
        self.session = make_session(self.cohort)
        self.s1 = User.objects.get(username="s1")
        self.s2 = User.objects.get(username="s2")

    def test_saving_a_register_from_the_view(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("take_attendance", kwargs={"pk": self.session.pk}), {
            f"student_{self.s1.pk}": "present", f"student_{self.s2.pk}": "absent",
        })
        self.assertEqual(self.session.records.count(), 2)
        self.assertEqual(self.session.records.get(student=self.s2).status, AttendanceRecord.Status.ABSENT)

    def test_mark_all_present_button(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("take_attendance", kwargs={"pk": self.session.pk}), {"action": "all_present"})
        self.assertEqual(self.session.records.filter(status=AttendanceRecord.Status.PRESENT).count(), 2)

    def test_blank_radio_skips_that_student(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse("take_attendance", kwargs={"pk": self.session.pk}), {
            f"student_{self.s1.pk}": "",
        })
        self.assertEqual(self.session.records.count(), 0)

    def test_session_marks_the_register_complete(self):
        self.client.force_login(self.teacher)
        counts = self.session.attendance_counts()
        self.assertEqual(counts["enrolled"], 2)
        self.assertEqual(counts["unmarked"], 2)
        self.session.mark_all_present(marked_by=self.teacher)
        self.assertEqual(self.session.attendance_counts()["unmarked"], 0)


class SeederTests(TestCase):
    def test_seed_demo_populates_school(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Cohort.objects.count(), 3)
        self.assertGreaterEqual(Session.objects.count(), 8)
        self.assertTrue(AttendanceRecord.objects.exists())
        self.assertTrue(Session.objects.filter(status=Session.Status.SCHEDULED).exists())
        self.assertTrue(Cohort.objects.filter(code__isnull=False).exists())
        self.assertTrue(Enrollment.objects.filter(active=True).exists())
