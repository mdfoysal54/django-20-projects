from django.db import transaction
from .models import Incident

class DomainError(ValueError):
    pass

@transaction.atomic
def page_incident(*, monitor, title, severity="sev2"):
    open_same = Incident.objects.filter(monitor=monitor, status__in=("open", "ack"), title=title)
    if open_same.exists():
        raise DomainError("An open incident already covers this signal.")
    return Incident.objects.create(monitor=monitor, title=title, severity=severity)

@transaction.atomic
def ack(incident):
    if incident.status != Incident.Status.OPEN:
        raise DomainError("Only open incidents can be acked.")
    incident.status = Incident.Status.ACK
    incident.save(update_fields=["status"])
    return incident

@transaction.atomic
def resolve(incident):
    if incident.status == Incident.Status.RES:
        raise DomainError("Already resolved.")
    incident.status = Incident.Status.RES
    incident.save(update_fields=["status"])
    return incident
