"""StayHub data models — hotels, rooms, guests and bookings.

The core domain rule: a room can never be double-booked. A booking occupies
[check_in, check_out) and availability is a pure date-range overlap test —
enforced twice: once in the form (friendly message) and once inside a
transaction with row locks (hard guarantee, race-proof).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def unique_slug(model, value, exclude_pk=None) -> str:
    base = slugify(value)[:50] or "item"
    slug, n = base, 1
    qs = model.objects.filter(slug=slug)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    while qs.exists():
        n += 1
        slug = f"{base}-{n}"
        qs = model.objects.filter(slug=slug)
    return slug


class Hotel(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hotels")
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True, editable=False)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    star_rating = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    amenities = models.CharField(max_length=300, blank=True, help_text="Comma-separated, e.g. WiFi, Pool, Gym")
    hero_emoji = models.CharField(max_length=8, default="🏨")
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Hotel, self.name, self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.hero_emoji} {self.name} ({self.city})"

    def get_absolute_url(self):
        return reverse("hotel_detail", kwargs={"slug": self.slug})

    @property
    def amenity_list(self) -> list[str]:
        return [a.strip() for a in self.amenities.split(",") if a.strip()]

    @property
    def stars(self) -> str:
        return "★" * self.star_rating + "☆" * (5 - self.star_rating)

    @property
    def room_count(self) -> int:
        return self.rooms.filter(is_active=True).count()

    @property
    def min_price(self):
        return self.rooms.filter(is_active=True).aggregate(m=models.Min("price_per_night"))["m"]

    @property
    def next_available(self) -> date:
        """First date on which at least one room is free (today if any room is)."""
        today = timezone.localdate()
        if self.available_rooms(today, today + timedelta(days=1)).exists():
            return today
        # Scan the next 90 days for the first free night.
        for offset in range(1, 90):
            day = today + timedelta(days=offset)
            if self.available_rooms(day, day + timedelta(days=1)).exists():
                return day
        return today + timedelta(days=90)

    def available_rooms(self, check_in: date, check_out: date):
        """Active rooms with no overlapping confirmed/pending booking."""
        return self.rooms.filter(is_active=True).exclude(
            bookings__status__in=Booking.BLOCKING_STATUSES,
            bookings__check_in__lt=check_out,
            bookings__check_out__gt=check_in,
        ).distinct()


class Room(models.Model):
    class RoomType(models.TextChoices):
        SINGLE = "single", "Single"
        DOUBLE = "double", "Double"
        TWIN = "twin", "Twin"
        SUITE = "suite", "Suite"
        FAMILY = "family", "Family"

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="rooms")
    number = models.CharField(max_length=12)
    room_type = models.CharField(max_length=10, choices=RoomType.choices, default=RoomType.DOUBLE)
    capacity = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1), MaxValueValidator(10)])
    price_per_night = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("1.00"))],
    )
    description = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("hotel", "number")
        ordering = ["hotel", "price_per_night"]

    def __str__(self):
        return f"{self.hotel.name} · Room {self.number} ({self.get_room_type_display()})"

    def is_available(self, check_in: date, check_out: date, exclude_booking_pk=None) -> bool:
        """True when no blocking booking overlaps [check_in, check_out)."""
        qs = self.bookings.filter(
            status__in=Booking.BLOCKING_STATUSES,
            check_in__lt=check_out,
            check_out__gt=check_in,
        )
        if exclude_booking_pk:
            qs = qs.exclude(pk=exclude_booking_pk)
        return not qs.exists()

    def price_for(self, nights: int) -> Decimal:
        return self.price_per_night * nights


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    BLOCKING_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.COMPLETED)
    BADGE = {Status.PENDING: "badge-warn", Status.CONFIRMED: "badge-ok",
             Status.CANCELLED: "badge-bad", Status.COMPLETED: "badge-info"}
    MAX_NIGHTS = 30

    guest = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    special_requests = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # Immutable price snapshot
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["room", "check_in", "check_out"])]

    def __str__(self):
        return f"Booking #{self.pk} · {self.room} · {self.check_in}→{self.check_out}"

    @property
    def reference(self) -> str:
        return f"SH-{self.pk:06d}"

    @property
    def nights(self) -> int:
        return max((self.check_out - self.check_in).days, 0)

    @property
    def status_badge(self) -> str:
        return self.BADGE.get(self.status, "badge-info")

    @property
    def is_upcoming(self) -> bool:
        return self.status in self.BLOCKING_STATUSES and self.check_in >= timezone.localdate()

    @property
    def can_cancel(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED) and self.check_in >= timezone.localdate()

    def get_absolute_url(self):
        return reverse("booking_detail", kwargs={"pk": self.pk})

    def clean(self):
        errors = {}
        if self.check_in and self.check_out:
            if self.check_out <= self.check_in:
                errors["check_out"] = "Check-out must be after check-in."
            elif self.nights > self.MAX_NIGHTS:
                errors["check_out"] = f"Stays are limited to {self.MAX_NIGHTS} nights."
            if self.check_in < timezone.localdate():
                errors["check_in"] = "Check-in cannot be in the past."
        if self.room_id and self.guests and self.guests > self.room.capacity:
            errors["guests"] = (
                f"Room {self.room.number} sleeps at most {self.room.capacity} guest(s)."
            )
        if errors:
            raise ValidationError(errors)

    @classmethod
    def create_booking(cls, *, guest, room, check_in, check_out, guests=1, special_requests="") -> "Booking":
        """Race-proof booking creation.

        Locks the room row, re-checks availability inside the transaction, then
        writes with the derived price snapshot.
        """
        with transaction.atomic():
            locked_room = Room.objects.select_for_update().get(pk=room.pk)
            if not locked_room.is_active:
                raise ValidationError("This room is not currently bookable.")
            if not locked_room.is_available(check_in, check_out):
                raise ValidationError("Sorry — this room was just booked for those dates.")
            booking = cls(
                guest=guest, room=locked_room, check_in=check_in, check_out=check_out,
                guests=guests, special_requests=special_requests,
            )
            booking.full_clean(exclude=["total_price"])
            booking.total_price = locked_room.price_for(booking.nights)
            booking.status = cls.Status.PENDING
            booking.save()
            return booking

    @classmethod
    def blocked_ranges(cls, room, start: date, days: int = 60) -> dict:
        """Map of date -> booking pk within the window (for the availability strip)."""
        end = start + timedelta(days=days)
        blocks = {}
        qs = cls.objects.filter(room=room, status__in=cls.BLOCKING_STATUSES,
                                check_in__lt=end, check_out__gt=start)
        for booking in qs:
            day = max(booking.check_in, start)
            while day < min(booking.check_out, end):
                blocks[day] = booking.pk
                day += timedelta(days=1)
        return blocks

