from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Appointment

class DomainError(ValueError):
    pass

@transaction.atomic
def book(*, client, stylist, service, start):
    if start < timezone.now() - timedelta(minutes=5):
        raise DomainError("Cannot book in the past.")
    end = start + timedelta(minutes=service.minutes)
    clash = Appointment.objects.filter(stylist=stylist, status__in=("book", "in"))
    for other in clash:
        o_end = other.start + timedelta(minutes=other.service.minutes)
        if start < o_end and end > other.start:
            raise DomainError(f"{stylist} is already in chair then.")
    return Appointment.objects.create(client=client, stylist=stylist, service=service, start=start)

@transaction.atomic
def complete(appt):
    if appt.status == Appointment.Status.CX:
        raise DomainError("Cancelled chairs cannot complete.")
    appt.status = Appointment.Status.DONE
    appt.save(update_fields=["status"])
    return appt
