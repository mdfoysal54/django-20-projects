"""EventTix models — events, ticket tiers and race-safe bookings."""
from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ON_SALE = "onsale", "On sale"
        SOLD_OUT = "soldout", "Sold out"
        CANCELLED = "cancelled", "Cancelled"

    organiser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=170, unique=True)
    venue = models.CharField(max_length=140)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    cover_emoji = models.CharField(max_length=8, default="🎟️")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("event_detail", kwargs={"slug": self.slug})

    @property
    def is_on_sale(self) -> bool:
        return self.status == self.Status.ON_SALE and self.starts_at > timezone.now()

    @property
    def total_capacity(self) -> int:
        return sum(t.capacity for t in self.tiers.all())

    @property
    def total_sold(self) -> int:
        return sum(t.sold for t in self.tiers.all())

    @property
    def remaining(self) -> int:
        return self.total_capacity - self.total_sold

    @property
    def sell_through(self) -> int:
        total = self.total_capacity
        return round(100 * self.total_sold / total) if total else 0


class TicketTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tiers")
    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                validators=[MinValueValidator(0)])
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    sold = models.PositiveIntegerField(default=0, editable=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "price"]
        constraints = [
            # The database itself refuses to oversell a tier.
            models.CheckConstraint(check=models.Q(sold__lte=models.F("capacity")), name="tier_sold_lte_capacity"),
        ]

    def __str__(self):
        return f"{self.name} ({self.price}) — {self.sold}/{self.capacity}"

    @property
    def remaining(self) -> int:
        return self.capacity - self.sold

    @property
    def is_available(self) -> bool:
        return self.remaining > 0


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=12, unique=True, editable=False)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="bookings")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.CONFIRMED)
    created = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    checked_in = models.PositiveIntegerField(default=0)
    lines = models.ManyToManyField(TicketTier, through="BookingLine", related_name="bookings")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.reference} — {self.quantity}× {self.event.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._new_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def _new_reference() -> str:
        alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
        while True:
            ref = "ET-" + "".join(secrets.choice(alphabet) for _ in range(8))
            if not Booking.objects.filter(reference=ref).exists():
                return ref

    @property
    def total(self):
        return self.unit_price * self.quantity

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.CONFIRMED

    def get_absolute_url(self):
        return reverse("booking_detail", kwargs={"reference": self.reference})

    # ------------------------------------------------------------- domain ops
    @classmethod
    def create_booking(cls, customer, event, tier, quantity):
        """Allocate `quantity` seats with row-level locking — never oversell.

        Returns (booking, None) on success or (None, error_message) on failure.
        """
        if quantity < 1:
            return None, "Choose at least one ticket."

        with transaction.atomic():
            # Lock the tier row; a concurrent booking waits here.
            locked = TicketTier.objects.select_for_update().get(pk=tier.pk)
            if event.status != Event.Status.ON_SALE:
                return None, "This event is not on sale."
            if locked.remaining < quantity:
                return None, (f"Only {locked.remaining} ticket(s) left in {locked.name}."
                              if locked.remaining else f"{locked.name} is sold out.")
            locked.sold += quantity
            locked.save(update_fields=["sold"])

            booking = cls.objects.create(customer=customer, event=event, quantity=quantity,
                                         unit_price=locked.price)
            BookingLine.objects.create(booking=booking, tier=locked, quantity=quantity,
                                       unit_price=locked.price)

            # Flip the event to sold-out once every tier is exhausted.
            if not event.tiers.filter(sold__lt=models.F("capacity")).exists():
                Event.objects.filter(pk=event.pk).update(status=Event.Status.SOLD_OUT)
        return booking, None

    def cancel(self):
        """Cancel and return seats to the pool atomically."""
        if self.status == self.Status.CANCELLED:
            return False
        with transaction.atomic():
            Booking.objects.select_for_update().filter(pk=self.pk).get()
            for line in self.booking_lines.select_related("tier"):
                TicketTier.objects.filter(pk=line.tier_id).update(sold=models.F("sold") - line.quantity)
            # Re-opening a sold-out event is intentional.
            Event.objects.filter(pk=self.event_id, status=Event.Status.SOLD_OUT).update(status=Event.Status.ON_SALE)
            self.status = self.Status.CANCELLED
            self.cancelled_at = timezone.now()
            self.save(update_fields=["status", "cancelled_at"])
        return True

    @property
    def qr_token(self) -> str:
        """Deterministic check-in token derived from the reference."""
        return hashlib.sha256(f"eventtix:{self.reference}:{settings.SECRET_KEY}".encode()).hexdigest()[:20]


class BookingLine(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="booking_lines")
    tier = models.ForeignKey(TicketTier, on_delete=models.PROTECT, related_name="lines")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
