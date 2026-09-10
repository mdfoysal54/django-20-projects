"""Seed MedCare with specialities, doctors, rotas and appointments."""
from datetime import time, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Appointment, Doctor, DoctorAvailability, Speciality

SPECIALITIES = [
    ("Cardiology", "cardiology", "❤️", "Heart and circulation."),
    ("Dermatology", "dermatology", "🧴", "Skin, hair and nails."),
    ("Paediatrics", "paediatrics", "🧒", "Care for infants, children and teens."),
    ("General Medicine", "general", "🩺", "Everyday illness and check-ups."),
    ("Orthopaedics", "orthopaedics", "🦴", "Bones, joints and sports injuries."),
]

DOCTORS = [
    ("dr_ayesha", "Ayesha", "Rahman", "cardiology", "950.00", 30, "C-201",
     "Interventional cardiologist with 14 years in the cath lab. Special interest in preventive cardiology.",
     [(0, time(9, 0), time(13, 0)), (2, time(15, 0), time(18, 0)), (4, time(9, 0), time(12, 0))]),
    ("dr_rakib", "Rakib", "Hasan", "dermatology", "700.00", 20, "D-104",
     "Clinical dermatologist focused on acne, eczema and paediatric skin conditions.",
     [(1, time(10, 0), time(14, 0)), (3, time(10, 0), time(14, 0)), (5, time(9, 0), time(12, 0))]),
    ("dr_nusrat", "Nusrat", "Jahan", "paediatrics", "800.00", 30, "P-310",
     "Paediatrician and newborn care specialist. Answering new-parent questions is the best part of the job.",
     [(0, time(14, 0), time(18, 0)), (2, time(9, 0), time(13, 0)), (4, time(14, 0), time(17, 0))]),
    ("dr_imran", "Imran", "Chowdhury", "general", "500.00", 15, "G-101",
     "General physician handling everything from fevers to diabetes reviews.",
     [(1, time(8, 0), time(12, 0)), (2, time(8, 0), time(12, 0)), (3, time(8, 0), time(12, 0)),
      (4, time(8, 0), time(12, 0))]),
    ("dr_sadia", "Sadia", "Karim", "orthopaedics", "1100.00", 30, "O-402",
     "Sports orthopaedic surgeon — knees, shoulders and return-to-play planning.",
     [(1, time(16, 0), time(19, 0)), (3, time(16, 0), time(19, 0))]),
]

PATIENTS = [
    ("patient", "Tanvir", "Ahmed", "Recurring chest tightness when climbing stairs."),
    ("patient2", "Marufa", "Akter", "Skin reaction that started after a new detergent."),
    ("patient3", "Sabbir", "Hossain", "Routine blood-pressure review and medication refill."),
]

REASONS = [
    "Follow-up on last month's test results",
    "New symptom that needs a look",
    "Annual health check-up",
    "Prescription renewal",
    "Second opinion on a previous diagnosis",
]


def upcoming_weekday(weekday: int, weeks: int = 1):
    today = timezone.localdate()
    delta = (weekday - today.weekday()) % 7 + 7 * weeks
    return today + timedelta(days=delta)


class Command(BaseCommand):
    help = "Create demo specialities, doctors, rotas and appointments."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for name, slug, emoji, description in SPECIALITIES:
            Speciality.objects.get_or_create(name=name, defaults={"slug": slug, "emoji": emoji,
                                                                  "description": description})

        for username, first, last, spec_slug, fee, slot, room, bio, rota in DOCTORS:
            user, created = User.objects.get_or_create(
                username=username, defaults={"first_name": first, "last_name": last,
                                             "email": f"{username}@medcare.dev"})
            if created:
                user.set_password("DemoPass123!")
                user.save()
            doctor, made = Doctor.objects.get_or_create(
                user=user, defaults={"speciality": Speciality.objects.get(slug=spec_slug),
                                     "fee": fee, "slot_minutes": slot, "room": room, "bio": bio})
            if made:
                for weekday, start, end in rota:
                    DoctorAvailability.objects.create(doctor=doctor, weekday=weekday,
                                                      start_time=start, end_time=end)

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@medcare.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        for username, first, last, _reason in PATIENTS:
            user, made = User.objects.get_or_create(username=username,
                                                    defaults={"first_name": first, "last_name": last,
                                                              "email": f"{username}@patient.dev"})
            if made:
                user.set_password("DemoPass123!")
                user.save()

        booked = completed = cancelled = 0
        for i, (username, _f, _l, _r) in enumerate(PATIENTS):
            patient = User.objects.get(username=username)
            doctor = Doctor.objects.order_by("user__username")[i % Doctor.objects.count()]
            # Find the doctor's next rota day and grab a free slot from it.
            for offset in range(0, 8):
                day = timezone.localdate() + timedelta(days=offset)
                slots = doctor.free_slots(day)
                if slots:
                    appointment, _err = Appointment.book(patient, doctor, slots[0], REASONS[i % len(REASONS)])
                    if appointment:
                        booked += 1
                    break

        # A completed visit with a clinical note, and a cancelled booking.
        doctor = Doctor.objects.get(user__username="dr_imran")
        patient = User.objects.get(username="patient3")
        for offset in range(0, 8):
            day = timezone.localdate() + timedelta(days=offset)
            slots = doctor.free_slots(day)
            if slots:
                appointment, _ = Appointment.book(patient, doctor, slots[-1], "Follow-up on medication")
                if appointment:
                    appointment.mark(Appointment.Status.COMPLETED,
                                     note="BP 128/82 on current dose. Continue, review in 8 weeks.")
                    completed += 1
                break

        doctor = Doctor.objects.get(user__username="dr_sadia")
        patient = User.objects.get(username="patient2")
        for offset in range(0, 8):
            day = timezone.localdate() + timedelta(days=offset)
            slots = doctor.free_slots(day)
            if slots:
                appointment, _ = Appointment.book(patient, doctor, slots[0], "Knee pain after running")
                if appointment:
                    appointment.cancel()
                    cancelled += 1
                break

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Speciality.objects.count()} specialities, {Doctor.objects.count()} doctors, "
            f"{Appointment.objects.count()} appointments ({booked} booked, {completed} completed, "
            f"{cancelled} cancelled)."
        ))
