from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Sum
from .models import Invoice, TimeEntry

class DomainError(ValueError):
    pass

def unbilled_minutes(matter):
    return matter.entries.filter(billed=False).aggregate(s=Sum("minutes"))["s"] or 0

@transaction.atomic
def log_time(matter, minutes, note):
    if matter.status == matter.Status.CLOSE:
        raise DomainError("Closed matters do not take time.")
    if minutes < 6:
        raise DomainError("Minimum slice is 6 minutes.")
    return TimeEntry.objects.create(matter=matter, minutes=minutes, note=note)

@transaction.atomic
def bill(matter):
    mins = unbilled_minutes(matter)
    if mins == 0:
        raise DomainError("Nothing to bill.")
    hours = Decimal(mins) / Decimal(60)
    amount = (hours * matter.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount > matter.retainer and matter.retainer > 0:
        # draw retainer first; remaining still billed
        pass
    inv = Invoice.objects.create(matter=matter, amount=amount)
    matter.entries.filter(billed=False).update(billed=True)
    if matter.retainer:
        draw = min(matter.retainer, amount)
        matter.retainer -= draw
    matter.status = matter.Status.BILL
    matter.save()
    return inv
