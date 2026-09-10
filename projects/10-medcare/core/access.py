"""MedCare role helpers — doctors, staff and patients."""
from .models import Doctor


def is_doctor(user) -> bool:
    if not user.is_authenticated:
        return False
    return Doctor.objects.filter(user=user).exists()


def doctor_for(user):
    if not user.is_authenticated:
        return None
    return Doctor.objects.filter(user=user).select_related("speciality").first()


def can_view_appointment(user, appointment) -> bool:
    """The patient, their doctor, and clinic staff may view; nobody else."""
    if not user.is_authenticated:
        return False
    if appointment.patient_id == user.pk:
        return True
    if appointment.doctor.user_id == user.pk:
        return True
    return user.is_staff
