"""TideTable — restaurant floor, reservations, kitchen."""
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

def money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class Venue(models.Model):
    name = models.CharField(max_length=120, default="Tide Table")
    theme = models.CharField(max_length=16, default="ember")
    @classmethod
    def get(cls):
        o, _ = cls.objects.get_or_create(pk=1)
        return o
    def __str__(self):
        return self.name

class DiningTable(models.Model):
    code = models.CharField(max_length=8, unique=True)
    seats = models.PositiveSmallIntegerField()
    zone = models.CharField(max_length=40, default="Main")
    def __str__(self):
        return f"{self.code} ({self.seats})"

class Guest(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24, blank=True)
    def __str__(self):
        return self.name

class Reservation(models.Model):
    class Status(models.TextChoices):
        BOOKED = "book", "Booked"
        SEATED = "seat", "Seated"
        DONE = "done", "Completed"
        NO_SHOW = "ns", "No-show"
        CX = "cx", "Cancelled"
    number = models.CharField(max_length=20, unique=True, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="reservations")
    table = models.ForeignKey(DiningTable, on_delete=models.PROTECT, related_name="reservations")
    party_size = models.PositiveSmallIntegerField()
    start = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.BOOKED)
    note = models.CharField(max_length=200, blank=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%Y%m%d")
            n = Reservation.objects.filter(number__startswith=f"RSV-{day}").count() + 1
            self.number = f"RSV-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("reservation_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class MenuItem(models.Model):
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    course = models.CharField(max_length=20, default="mains")
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class Ticket(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="tickets")
    sent_at = models.DateTimeField(auto_now_add=True)
    fired = models.BooleanField(default=False)

class TicketLine(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    qty = models.PositiveSmallIntegerField(default=1)
