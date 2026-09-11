from django.db import transaction
from .models import Parcel, Scan

class DomainError(ValueError):
    pass

MAX_KG = 30

@transaction.atomic
def intake(*, sender, recipient, dest_city, weight_kg, origin, cod=0):
    if float(weight_kg) <= 0:
        raise DomainError("Weight must be positive.")
    if float(weight_kg) > MAX_KG:
        raise DomainError("Parcels over 30 kg need freight, not last-mile.")
    p = Parcel.objects.create(sender=sender, recipient=recipient, dest_city=dest_city,
                              weight_kg=weight_kg, origin=origin, cod=cod)
    Scan.objects.create(parcel=p, kind="created", note=origin.name)
    return p

@transaction.atomic
def advance(parcel, courier=None):
    order = [Parcel.Status.CREATED, Parcel.Status.HUB, Parcel.Status.OUT, Parcel.Status.DONE]
    if parcel.status == Parcel.Status.RET:
        raise DomainError("Returned parcels stay returned.")
    if parcel.status == Parcel.Status.DONE:
        raise DomainError("Already delivered.")
    nxt = order[order.index(parcel.status) + 1]
    if nxt == Parcel.Status.OUT and courier is None and parcel.courier is None:
        raise DomainError("Assign a courier before last-mile.")
    if courier:
        if courier.station_id != parcel.origin_id and nxt == Parcel.Status.HUB:
            pass
        parcel.courier = courier
    parcel.status = nxt
    parcel.save()
    Scan.objects.create(parcel=parcel, kind=nxt, note=str(parcel.courier or ""))
    return parcel
