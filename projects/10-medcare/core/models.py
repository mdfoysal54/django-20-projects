"""MedCare models — clinics, doctors, weekly availability and race-safe appointments."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone


class Speciality(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    emoji = models.CharField(max_length=8, default="🩺")
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Specialities"

    def __str__(self):
        return self.name


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    speciality = models.ForeignKey(Speciality, on_delete=models.PROTECT, related_name="doctors")
    bio = models.TextField(blank=True)
    fee = models.DecimalField(max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    slot_minutes = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(10)])
    room = models.CharField(max_length=20, blank=True)
    accepting_new = models.BooleanField(default=True)

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"

    def get_absolute_url(self):
        return reverse("doctor_detail", kwargs={"pk": self.pk})

    @property
    def display_name(self) -> str:
        return f"Dr. {self.user.get_full_name() or self.user.username}"

    # ------------------------------------------------------------ availability
    def blocks_for(self, weekday: int):
        return self.availability.filter(weekday=weekday, active=True).order_by("start_time")

    def _iter_slots(self, day):
        """Yield aware datetimes for every slot the weekly rota defines on `day`."""
        for block in self.blocks_for(day.weekday()):
            cursor = timezone.make_aware(datetime.combine(day, block.start_time))
            end = timezone.make_aware(datetime.combine(day, block.end_time))
            step = timedelta(minutes=self.slot_minutes)
            while cursor + step <= end:
                yield cursor
                cursor += step

    def free_slots(self, day, ignore_pk=None):
        """Slots on `day` that are neither past nor already taken."""
        now = timezone.now()
        taken = set(self.appointments.filter(
            starts_at__date=day, status__in=Appointment.ACTIVE_STATUSES
        ).exclude(pk=ignore_pk).values_list("starts_at", flat=True))
        return [s for s in self._iter_slots(day) if s > now and s not in taken]

    def slot_is_bookable(self, starts_at, ignore_pk=None) -> bool:
        day = timezone.localtime(starts_at).date()
        return starts_at in self.free_slots(day, ignore_pk=ignore_pk)


class DoctorAvailability(models.Model):
    """A weekly rota block, e.g. Mon 09:00–13:00 in the doctor's local time."""

    WEEKDAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
                (4, "Friday"), (5, "Saturday"), (6, "Sunday")]

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(check=models.Q(end_time__gt=models.F("start_time")),
                                   name="availability_end_after_start"),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No show"

    ACTIVE_STATUSES = (Status.BOOKED, Status.COMPLETED)

    reference = models.CharField(max_length=14, unique=True, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.BOOKED)
    clinical_note = models.TextField(blank=True, help_text="Doctor-only note — never shown to the patient.")
    created = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["doctor", "starts_at"]), models.Index(fields=["patient", "starts_at"])]
        constraints = [
            # A doctor can hold at most one non-cancelled appointment per start time.
            models.UniqueConstraint(fields=["doctor", "starts_at"],
                                    condition=models.Q(status__in=["booked", "completed"]),
                                    name="doctor_slot_unique"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.patient.username} with {self.doctor} at {self.starts_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._new_reference()
        if not self.ends_at:
            self.ends_at = self.starts_at + timedelta(minutes=self.doctor.slot_minutes)
        super().save(*args, **kwargs)

    @staticmethod
    def _new_reference() -> str:
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        while True:
            ref = "MC" + "".join(secrets.choice(alphabet) for _ in range(8))
            if not Appointment.objects.filter(reference=ref).exists():
                return ref

    def get_absolute_url(self):
        return reverse("appointment_detail", kwargs={"reference": self.reference})

    @property
    def is_active(self) -> bool:
        return self.status in self.ACTIVE_STATUSES

    @property
    def is_past(self) -> bool:
        return self.starts_at < timezone.now()

    @property
    def is_today(self) -> bool:
        return timezone.localtime(self.starts_at).date() == timezone.localdate()

    # -------------------------------------------------------------- domain ops
    @classmethod
    def book(cls, patient, doctor, starts_at, reason):
        """Book a slot, or return (None, reason why not).

        Protects against: past slots, slots outside the rota, an already-taken
        slot (row lock + unique constraint) and the patient double-booking
        themselves at an overlapping time.
        """
        if starts_at <= timezone.now():
            return None, "That time has already passed — pick a later slot."
        day = timezone.localtime(starts_at).date()
        if starts_at not in doctor._iter_slots(day):
            return None, "That time is outside the doctor's published hours."

        ends_at = starts_at + timedelta(minutes=doctor.slot_minutes)
        try:
            with transaction.atomic():
                # Patient overlap: same patient, overlapping window, active booking.
                clash = cls.objects.select_for_update().filter(
                    patient=patient, status__in=cls.ACTIVE_STATUSES,
                    starts_at__lt=ends_at, ends_at__gt=starts_at,
                ).exists()
                if clash:
                    return None, "You already have an appointment at that time."
                return cls.objects.create(patient=patient, doctor=doctor, starts_at=starts_at,
                                          ends_at=ends_at, reason=reason), None
        except IntegrityError:
            # The unique constraint fired: someone grabbed the slot first.
            return None, "Sorry — that slot was just taken. Please pick another."

    def cancel(self, by=None):
        if self.status in (self.Status.CANCELLED,):
            return False
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at"])
        return True

    def mark(self, status, note=""):
        """Doctor-only outcome recording (completed / no_show / booked)."""
        if status not in dict(self.Status.choices):
            raise ValueError("Unknown status")
        self.status = status
        if note:
            self.clinical_note = note
        self.save(update_fields=["status", "clinical_note"])
        return self
