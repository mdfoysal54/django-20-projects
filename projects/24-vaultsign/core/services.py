from django.db import transaction
from django.utils import timezone
from .models import Envelope, Event, Signer

class DomainError(ValueError):
    pass

@transaction.atomic
def send(envelope):
    if envelope.status != Envelope.Status.DRAFT:
        raise DomainError("Only drafts can be sent.")
    if envelope.signers.count() < 1:
        raise DomainError("Add at least one signer.")
    envelope.status = Envelope.Status.SENT
    envelope.save()
    Event.objects.create(envelope=envelope, kind="sent")
    return envelope

@transaction.atomic
def sign(envelope, email):
    if envelope.status == Envelope.Status.VOID:
        raise DomainError("Void envelopes cannot be signed.")
    if envelope.status != Envelope.Status.SENT:
        raise DomainError("Send the envelope first.")
    signer = envelope.signers.filter(email__iexact=email).first()
    if not signer:
        raise DomainError("That email is not on this envelope.")
    if signer.signed_at:
        raise DomainError("Already signed.")
    signer.signed_at = timezone.now()
    signer.save()
    Event.objects.create(envelope=envelope, kind="signed", note=email)
    if envelope.signers.filter(signed_at__isnull=True).count() == 0:
        envelope.status = Envelope.Status.SIGNED
        envelope.save()
        Event.objects.create(envelope=envelope, kind="complete")
    return envelope

@transaction.atomic
def void(envelope):
    if envelope.status == Envelope.Status.SIGNED:
        raise DomainError("Completed envelopes are immutable.")
    envelope.status = Envelope.Status.VOID
    envelope.save()
    Event.objects.create(envelope=envelope, kind="void")
    return envelope
