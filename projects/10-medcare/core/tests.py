"""MedCare domain tests — no double-booking, rota enforcement, privacy of notes."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Doctor, DoctorAvailability, Speciality


def next_weekday(weekday: int, weeks_ahead: int = 1) -> date:
    """The next date (at least a week out) landing on `weekday`."""
    today = timezone.localdate()
    delta = (weekday - today.weekday()) % 7 + 7 * weeks_ahead
    return today + timedelta(days=delta)


def at(day: date, hour: int, minute: int = 0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


def make_doctor(username="doc", speciality="Cardiology", slot_minutes=30, weekday=0,
                start=time(9, 0), end=time(12, 0)):
    user = User.objects.create_user(username, password="Str0ng!Passw0rd", first_name="Ayesha", last_name="Rahman")
    spec, _ = Speciality.objects.get_or_create(name=speciality, defaults={"slug": speciality.lower()})
    doctor = Doctor.objects.create(user=user, speciality=spec, fee="800.00", slot_minutes=slot_minutes, room="A1")
    DoctorAvailability.objects.create(doctor=doctor, weekday=weekday, start_time=start, end_time=end)
    return doctor


class SlotGenerationTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor(weekday=0)          # Mondays 09:00–12:00, 30-min slots

    def test_slots_follow_the_rota(self):
        day = next_weekday(0)
        slots = self.doctor.free_slots(day)
        self.assertEqual(len(slots), 6)               # 09:00 … 11:30
        self.assertEqual(timezone.localtime(slots[0]).time(), time(9, 0))
        self.assertEqual(timezone.localtime(slots[-1]).time(), time(11, 30))

    def test_non_working_day_has_no_slots(self):
        self.assertEqual(self.doctor.free_slots(next_weekday(2)), [])

    def test_past_slots_are_not_offered(self):
        today = timezone.localdate()
        if today.weekday() == 0:                      # only meaningful on a Monday
            self.assertTrue(all(s > timezone.now() for s in self.doctor.free_slots(today)))

    def test_booked_slot_disappears_from_free_slots(self):
        day = next_weekday(0)
        patient = User.objects.create_user("pat", password="Str0ng!Passw0rd")
        slot = self.doctor.free_slots(day)[0]
        Appointment.book(patient, self.doctor, slot, "Chest pain follow-up")
        self.assertNotIn(slot, self.doctor.free_slots(day))
        self.assertEqual(len(self.doctor.free_slots(day)), 5)


class BookingRulesTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = User.objects.create_user("patient", password="Str0ng!Passw0rd")
        self.other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        self.day = next_weekday(0)

    def test_book_creates_appointment_with_reference_and_end_time(self):
        slot = self.doctor.free_slots(self.day)[0]
        appointment, error = Appointment.book(self.patient, self.doctor, slot, "Annual check-up")
        self.assertIsNone(error)
        self.assertTrue(appointment.reference.startswith("MC"))
        self.assertEqual(appointment.ends_at - appointment.starts_at, timedelta(minutes=30))
        self.assertEqual(appointment.status, Appointment.Status.BOOKED)

    def test_double_booking_the_same_slot_is_refused(self):
        slot = self.doctor.free_slots(self.day)[0]
        Appointment.book(self.patient, self.doctor, slot, "Annual check-up")
        clash, error = Appointment.book(self.other, self.doctor, slot, "Also wants the slot")
        self.assertIsNone(clash)
        self.assertIn("just taken", error)
        self.assertEqual(self.doctor.appointments.count(), 1)

    def test_database_constraint_blocks_a_forced_double_booking(self):
        slot = self.doctor.free_slots(self.day)[0]
        Appointment.objects.create(patient=self.patient, doctor=self.doctor, starts_at=slot,
                                   ends_at=slot + timedelta(minutes=30), reason="First")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Appointment.objects.create(patient=self.other, doctor=self.doctor, starts_at=slot,
                                           ends_at=slot + timedelta(minutes=30), reason="Second")

    def test_patient_cannot_overlap_themselves_with_two_doctors(self):
        doctor2 = make_doctor(username="doc2", speciality="Dermatology", weekday=0)
        slot = self.doctor.free_slots(self.day)[0]
        Appointment.book(self.patient, self.doctor, slot, "First visit")
        second, error = Appointment.book(self.patient, doctor2, slot, "Second opinion")
        self.assertIsNone(second)
        self.assertIn("already have an appointment", error)

    def test_back_to_back_appointments_are_allowed(self):
        doctor2 = make_doctor(username="doc2", speciality="Dermatology", weekday=0)
        first_slot = self.doctor.free_slots(self.day)[0]
        Appointment.book(self.patient, self.doctor, first_slot, "First visit")
        second_slot = first_slot + timedelta(minutes=30)   # ends exactly when the first ends
        appointment, error = Appointment.book(self.patient, doctor2, second_slot, "Second opinion")
        self.assertIsNone(error)
        self.assertIsNotNone(appointment)

    def test_cannot_book_outside_published_hours(self):
        appointment, error = Appointment.book(self.patient, self.doctor, at(self.day, 14, 0), "Lunchtime slot")
        self.assertIsNone(appointment)
        self.assertIn("published hours", error)

    def test_cannot_book_in_the_past(self):
        past = timezone.now() - timedelta(days=1)
        appointment, error = Appointment.book(self.patient, self.doctor, past, "Time travel")
        self.assertIsNone(appointment)
        self.assertIn("already passed", error)

    def test_cancelling_frees_the_slot(self):
        slot = self.doctor.free_slots(self.day)[0]
        appointment, _ = Appointment.book(self.patient, self.doctor, slot, "To be cancelled")
        self.assertTrue(appointment.cancel())
        self.assertFalse(appointment.cancel())             # idempotent
        self.assertIn(slot, self.doctor.free_slots(self.day))

    def test_completed_appointment_still_blocks_the_slot(self):
        slot = self.doctor.free_slots(self.day)[0]
        appointment, _ = Appointment.book(self.patient, self.doctor, slot, "Done visit")
        appointment.mark(Appointment.Status.COMPLETED)
        self.assertNotIn(slot, self.doctor.free_slots(self.day))   # history preserved


class PrivacyTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = User.objects.create_user("patient", password="Str0ng!Passw0rd")
        self.stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.staff = User.objects.create_user("staff", password="Str0ng!Passw0rd", is_staff=True)
        slot = self.doctor.free_slots(next_weekday(0))[0]
        self.appointment, _ = Appointment.book(self.patient, self.doctor, slot, "Private matter")
        self.appointment.mark(Appointment.Status.COMPLETED, note="Patient reports improvement.")

    def test_patient_sees_own_appointment_without_the_clinical_note(self):
        self.client.force_login(self.patient)
        response = self.client.get(self.appointment.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Patient reports improvement")

    def test_doctor_sees_the_clinical_note(self):
        self.client.force_login(self.doctor.user)
        response = self.client.get(self.appointment.get_absolute_url())
        self.assertContains(response, "Patient reports improvement")

    def test_stranger_gets_404(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(self.appointment.get_absolute_url()).status_code, 404)

    def test_stranger_cannot_post_a_clinical_note(self):
        self.client.force_login(self.stranger)
        response = self.client.post(reverse("update_note", kwargs={"reference": self.appointment.reference}),
                                    {"status": "no_show", "clinical_note": "Hacked"})
        self.assertEqual(response.status_code, 404)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)
        self.assertNotIn("Hacked", self.appointment.clinical_note)

    def test_patient_cannot_cancel_someone_elses_appointment(self):
        self.client.force_login(self.stranger)
        response = self.client.post(reverse("cancel", kwargs={"reference": self.appointment.reference}))
        self.assertEqual(response.status_code, 404)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.COMPLETED)

    def test_clinic_schedule_is_doctor_only(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("schedule"))
        self.assertEqual(response.status_code, 302)       # bounced
        self.client.force_login(self.doctor.user)
        self.assertEqual(self.client.get(reverse("schedule")).status_code, 200)


class BookingViewTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor()
        self.patient = User.objects.create_user("patient", password="Str0ng!Passw0rd")
        self.day = next_weekday(0)

    def test_booking_via_the_web_flow(self):
        self.client.force_login(self.patient)
        slot = self.doctor.free_slots(self.day)[0]
        response = self.client.post(reverse("book", kwargs={"pk": self.doctor.pk}),
                                    {"doctor": self.doctor.pk, "starts_at": slot.isoformat(),
                                     "reason": "Persistent cough for two weeks"})
        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.patient, self.patient)

    def test_patient_cannot_be_double_booked_through_the_ui(self):
        self.client.force_login(self.patient)
        slot = self.doctor.free_slots(self.day)[0]
        payload = {"doctor": self.doctor.pk, "starts_at": slot.isoformat(), "reason": "First booking here"}
        self.client.post(reverse("book", kwargs={"pk": self.doctor.pk}), payload)
        response = self.client.post(reverse("book", kwargs={"pk": self.doctor.pk}), payload, follow=True)
        self.assertEqual(Appointment.objects.count(), 1)
        # Re-posting the same slot is refused by the patient-overlap guard.
        self.assertContains(response, "already have an appointment")

    def test_doctor_detail_does_not_offer_past_dates(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("doctor_detail", kwargs={"pk": self.doctor.pk}),
                                   {"date": (timezone.localdate() - timedelta(days=3)).isoformat()})
        self.assertEqual(response.status_code, 200)       # clamped to today
        self.assertContains(response, "cannot book a slot in the past")


class SeederTests(TestCase):
    def test_seed_demo_populates_clinic(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Doctor.objects.count(), 5)
        self.assertTrue(DoctorAvailability.objects.exists())
        self.assertTrue(Appointment.objects.filter(status=Appointment.Status.BOOKED).exists())
        self.assertTrue(Appointment.objects.filter(status=Appointment.Status.COMPLETED).exists())
        self.assertTrue(Appointment.objects.filter(status=Appointment.Status.CANCELLED).exists())
        self.assertTrue(all(d.availability.exists() for d in Doctor.objects.all()))
