"""TideTable domain."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from .models import Reservation, Ticket, TicketLine

class DomainError(ValueError):
    pass

WINDOW = timedelta(minutes=90)

@transaction.atomic
def book(*, guest, table, party_size, start, note=""):
    if party_size < 1:
        raise DomainError("Party size must be at least 1.")
    if party_size > table.seats:
        raise DomainError(f"{table.code} only seats {table.seats}.")
    clash = Reservation.objects.filter(table=table, status__in=(Reservation.Status.BOOKED, Reservation.Status.SEATED)).filter(
        start__lt=start + WINDOW, start__gt=start - WINDOW)
    if clash.exists():
        raise DomainError("That table is already reserved in this window.")
    return Reservation.objects.create(guest=guest, table=table, party_size=party_size, start=start, note=note)

@transaction.atomic
def fire_ticket(reservation, items):
    if reservation.status == Reservation.Status.CX:
        raise DomainError("Cancelled covers cannot go to the kitchen.")
    if not items:
        raise DomainError("Add at least one dish.")
    ticket = Ticket.objects.create(reservation=reservation, fired=True)
    for item, qty in items:
        TicketLine.objects.create(ticket=ticket, item=item, qty=qty)
    reservation.status = Reservation.Status.SEATED
    reservation.save(update_fields=["status"])
    return ticket
