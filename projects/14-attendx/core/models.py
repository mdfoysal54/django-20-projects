"""AttendX models — cohorts, enrolments, class sessions and attendance registers."""
from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Cohort(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cohorts")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=8, unique=True, editable=False)
    subject = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    room = models.CharField(max_length=40, blank=True)
    meeting_note = models.CharField(max_length=120, blank=True, help_text="e.g. 'Sun & Tue, 10:00–11:30'")
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, through="Enrollment", related_name="cohorts_joined")
    created = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["teacher", "name"], name="cohort_name_unique_per_teacher")]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._new_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _new_code() -> str:
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if not Cohort.objects.filter(code=code).exists():
                return code

    def get_absolute_url(self):
        return reverse("cohort_detail", kwargs={"pk": self.pk})

    @property
    def student_count(self) -> int:
        return self.enrollments.filter(active=True).count()

    @property
    def session_count(self) -> int:
        return self.sessions.filter(status=Session.Status.HELD).count()

    def enrolled_students(self):
        return (settings.AUTH_USER_MODEL and
                [e.student for e in self.enrollments.filter(active=True).select_related("student")])

    def can_be_managed_by(self, user) -> bool:
        return user.is_authenticated and (user == self.teacher or user.is_staff)

    def is_enrolled(self, user) -> bool:
        return user.is_authenticated and self.enrollments.filter(student=user, active=True).exists()

    def join(self, user):
        """Enrol a student by cohort code. Idempotent — re-joining is a no-op."""
        if not user.is_authenticated:
            return None, "Log in to join a class."
        if user == self.teacher:
            return None, "You teach this cohort."
        enrollment, created = Enrollment.objects.get_or_create(cohort=self, student=user,
                                                              defaults={"active": True})
        if not created and not enrollment.active:
            enrollment.active = True
            enrollment.save(update_fields=["active"])
            created = True
        return enrollment, None if created else "You are already enrolled in this cohort."

    def attendance_summary(self):
        """Cohort-wide attendance: attended / counted sessions per student."""
        held = self.sessions.filter(status=Session.Status.HELD)
        total_sessions = held.count()
        rows = []
        for enrollment in self.enrollments.filter(active=True).select_related("student"):
            records = AttendanceRecord.objects.filter(session__in=held, student=enrollment.student)
            present = records.filter(status=AttendanceRecord.Status.PRESENT).count()
            late = records.filter(status=AttendanceRecord.Status.LATE).count()
            absent = records.filter(status=AttendanceRecord.Status.ABSENT).count()
            excused = records.filter(status=AttendanceRecord.Status.EXCUSED).count()
            counted = total_sessions - excused          # excused absences leave the denominator
            attended = present + late                   # being late still counts as attending
            rate = round(100 * attended / counted) if counted else None
            rows.append({"student": enrollment.student, "present": present, "late": late,
                         "absent": absent, "excused": excused, "attended": attended,
                         "rate": rate, "unmarked": max(0, counted - present - late - absent)})
        return {"total_sessions": total_sessions, "rows": sorted(rows, key=lambda r: (r["rate"] is None, r["rate"] or 0))}


class Enrollment(models.Model):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    active = models.BooleanField(default=True)
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student__username"]
        constraints = [models.UniqueConstraint(fields=["cohort", "student"], name="one_enrollment_per_student")]

    def __str__(self):
        return f"{self.student.username} in {self.cohort.name}"


class Session(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        HELD = "held", "Held"
        CANCELLED = "cancelled", "Cancelled"

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="sessions")
    date = models.DateField(default=timezone.localdate)
    topic = models.CharField(max_length=140, blank=True)
    starts_at = models.TimeField(null=True, blank=True)
    ends_at = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.SCHEDULED)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "starts_at"]
        constraints = [models.UniqueConstraint(fields=["cohort", "date", "topic"], name="one_session_per_topic_per_day")]

    def __str__(self):
        return f"{self.cohort.name} — {self.date}"

    def get_absolute_url(self):
        return reverse("session_detail", kwargs={"pk": self.pk})

    @property
    def is_today(self) -> bool:
        return self.date == timezone.localdate()

    @property
    def is_future(self) -> bool:
        return self.date > timezone.localdate()

    def can_mark(self) -> bool:
        """Attendance can only be recorded for sessions that have actually happened."""
        return self.status == self.Status.HELD and not self.is_future

    def mark(self, student, status, marked_by=None):
        """Record or update one student's attendance (idempotent per student)."""
        if status not in dict(AttendanceRecord.Status.choices):
            raise ValueError("Unknown attendance status")
        if not self.cohort.is_enrolled(student):
            raise ValueError("That student is not enrolled in this cohort.")
        record, _created = AttendanceRecord.objects.update_or_create(
            session=self, student=student,
            defaults={"status": status, "marked_by": marked_by, "marked_at": timezone.now()},
        )
        return record

    @transaction.atomic
    def mark_all_present(self, marked_by=None):
        """Convenience: mark every enrolled student present (then adjust exceptions)."""
        for enrollment in self.cohort.enrollments.filter(active=True):
            self.mark(enrollment.student, AttendanceRecord.Status.PRESENT, marked_by)
        return self.records.count()

    def attendance_counts(self):
        counts = {key: 0 for key, _label in AttendanceRecord.Status.choices}
        for record in self.records.all():
            counts[record.status] += 1
        counts["enrolled"] = self.cohort.student_count
        counts["unmarked"] = max(0, counts["enrolled"] - len([r for r in self.records.all()]))
        return counts

    @property
    def attendance_rate(self):
        records = list(self.records.all())
        if not records:
            return None
        attended = len([r for r in records if r.status in AttendanceRecord.ATTENDED_STATUSES])
        counted = len([r for r in records if r.status != AttendanceRecord.Status.EXCUSED])
        return round(100 * attended / counted) if counted else None


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        EXCUSED = "excused", "Excused"

    #: Late still counts as attending; excused is removed from the denominator.
    ATTENDED_STATUSES = (Status.PRESENT, Status.LATE)

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records")
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PRESENT)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="marked_records")
    marked_at = models.DateTimeField(auto_now=True)
    note = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["student__username"]
        constraints = [models.UniqueConstraint(fields=["session", "student"], name="one_record_per_student_per_session")]

    def __str__(self):
        return f"{self.student.username}: {self.get_status_display()}"


def student_report(student):
    """Per-student attendance across every cohort they're enrolled in."""
    rows = []
    total_attended = total_counted = 0
    for enrollment in student.enrollments.filter(active=True).select_related("cohort"):
        cohort = enrollment.cohort
        held = cohort.sessions.filter(status=Session.Status.HELD)
        records = AttendanceRecord.objects.filter(student=student, session__in=held)
        excused = records.filter(status=AttendanceRecord.Status.EXCUSED).count()
        present = records.filter(status=AttendanceRecord.Status.PRESENT).count()
        late = records.filter(status=AttendanceRecord.Status.LATE).count()
        counted = held.count() - excused
        total_attended += present + late
        total_counted += counted
        rows.append({
            "cohort": cohort,
            "held": held.count(),
            "present": present,
            "late": late,
            "absent": records.filter(status=AttendanceRecord.Status.ABSENT).count(),
            "excused": excused,
            "rate": round(100 * (present + late) / counted) if counted else None,
        })
    overall = round(100 * total_attended / total_counted) if total_counted else None
    return {"rows": rows, "overall_rate": overall,
            "total_attended": total_attended, "total_counted": total_counted}


def rate_band(rate):
    """Label a percentage for the UI: good / warning / critical."""
    if rate is None:
        return "none"
    if rate >= 85:
        return "ok"
    if rate >= 70:
        return "warn"
    return "danger"
