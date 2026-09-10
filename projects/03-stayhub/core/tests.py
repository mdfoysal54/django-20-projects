"""StayHub domain tests — the double-booking guarantees are the headline."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Hotel, Room


def d(offset):
    return timezone.localdate() + timedelta(days=offset)


def make_hotel(owner, name="Test Hotel", city="Dhaka", **kw):
    return Hotel.objects.create(owner=owner, name=name, city=city, **kw)


def make_room(hotel, number="101", price="100.00", capacity=2, **kw):
    return Room.objects.create(
        hotel=hotel, number=number, price_per_night=Decimal(price), capacity=capacity, **kw
    )


class AvailabilityMathTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.guest = User.objects.create_user("guest", password="Str0ng!Passw0rd")
        self.hotel = make_hotel(self.owner)
        self.room = make_room(self.hotel)

    def test_overlap_semantics(self):
        Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(8))
        # Overlapping windows are blocked
        self.assertFalse(self.room.is_available(d(5), d(8)))    # exact same dates
        self.assertFalse(self.room.is_available(d(6), d(7)))    # fully inside
        self.assertFalse(self.room.is_available(d(7), d(10)))   # overlapping tail
        self.assertFalse(self.room.is_available(d(3), d(6)))    # overlapping head
        self.assertFalse(self.room.is_available(d(4), d(9)))    # superset
        # Back-to-back is allowed: checkout day == next checkin day
        self.assertTrue(self.room.is_available(d(3), d(5)))     # ends the day it starts
        self.assertTrue(self.room.is_available(d(8), d(10)))    # starts the day it ends
        self.assertTrue(self.room.is_available(d(20), d(22)))   # far future

    def test_cancelled_bookings_free_the_dates(self):
        booking = Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(8))
        self.assertFalse(self.room.is_available(d(5), d(8)))
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        self.assertTrue(self.room.is_available(d(5), d(8)))

    def test_second_overlapping_booking_is_rejected(self):
        Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(8))
        with self.assertRaises(ValidationError):
            Booking.create_booking(guest=self.guest, room=self.room, check_in=d(4), check_out=d(9))
        self.assertEqual(Booking.objects.count(), 1)

    def test_total_price_is_snapshot_of_nights(self):
        booking = Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(8))
        self.assertEqual(booking.nights, 3)
        self.assertEqual(booking.total_price, Decimal("300.00"))
        # A later price change does not rewrite history
        self.room.price_per_night = Decimal("999.00")
        self.room.save()
        booking.refresh_from_db()
        self.assertEqual(booking.total_price, Decimal("300.00"))

    def test_validation_rules(self):
        with self.assertRaises(ValidationError):
            Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(5))  # zero nights
        with self.assertRaises(ValidationError):
            Booking.create_booking(guest=self.guest, room=self.room, check_in=d(-1), check_out=d(2))  # past
        with self.assertRaises(ValidationError):
            Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(5 + 31),
                                   guests=1)  # too many nights
        with self.assertRaises(ValidationError):
            Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(7),
                                   guests=5)  # over capacity

    def test_available_rooms_excludes_booked(self):
        second = make_room(self.hotel, number="102")
        Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(8))
        free = list(self.hotel.available_rooms(d(5), d(8)))
        self.assertIn(second, free)
        self.assertNotIn(self.room, free)


class SearchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.hotel = make_hotel(self.owner, "Sea View Inn", city="Cox's Bazar")
        self.room = make_room(self.hotel, price="80.00")

    def test_city_search(self):
        response = self.client.get(reverse("search"), {"city": "cox"})
        self.assertContains(response, "Sea View Inn")
        response = self.client.get(reverse("search"), {"city": "nowhere"})
        self.assertNotContains(response, "Sea View Inn")

    def test_search_hides_fully_booked_hotels(self):
        Booking.create_booking(
            guest=User.objects.create_user("g", password="Str0ng!Passw0rd"),
            room=self.room, check_in=d(3), check_out=d(6),
        )
        response = self.client.get(reverse("search"), {"check_in": d(4), "check_out": d(5)})
        self.assertNotContains(response, "Sea View Inn")
        response = self.client.get(reverse("search"), {"check_in": d(7), "check_out": d(8)})
        self.assertContains(response, "Sea View Inn")

    def test_invalid_date_range_rejected(self):
        response = self.client.get(reverse("search"), {"check_in": d(10), "check_out": d(9)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check-out must be after check-in")

    def test_past_checkin_rejected(self):
        response = self.client.get(reverse("search"), {"check_in": d(-2), "check_out": d(1)})
        self.assertContains(response, "cannot be in the past")


class BookingFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.guest = User.objects.create_user("guest", password="Str0ng!Passw0rd")
        self.hotel = make_hotel(self.owner)
        self.room = make_room(self.hotel, price="120.00", capacity=3)

    def url(self, **params):
        base = reverse("booking_create", kwargs={"room_pk": self.room.pk})
        return f"{base}?check_in={d(5)}&check_out={d(7)}"

    def test_booking_requires_login(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_full_booking_flow_via_http(self):
        self.client.force_login(self.guest)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "240.00")   # 2 nights × 120

        response = self.client.post(self.url(), {"guests": 2, "special_requests": "High floor"})
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get()
        self.assertEqual(booking.guest, self.guest)
        self.assertEqual(booking.total_price, Decimal("240.00"))
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_booking_page_shows_conflict_notice(self):
        other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        Booking.create_booking(guest=other, room=self.room, check_in=d(5), check_out=d(7))
        self.client.force_login(self.guest)
        response = self.client.get(self.url(), follow=True)
        self.assertContains(response, "already booked")

    def test_http_booking_blocked_when_room_taken(self):
        other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        Booking.create_booking(guest=other, room=self.room, check_in=d(5), check_out=d(7))
        self.client.force_login(self.guest)
        response = self.client.post(self.url(), {"guests": 1})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)

    def test_capacity_cannot_be_exceeded_via_form(self):
        self.client.force_login(self.guest)
        response = self.client.post(self.url(), {"guests": 9})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_ownership(self):
        booking = Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(7))
        stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(reverse("booking_detail", kwargs={"pk": booking.pk})).status_code, 404)
        self.assertEqual(self.client.post(reverse("booking_cancel", kwargs={"pk": booking.pk})).status_code, 404)

    def test_cancel_releases_dates(self):
        self.client.force_login(self.guest)
        booking = Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(7))
        response = self.client.post(reverse("booking_cancel", kwargs={"pk": booking.pk}))
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertTrue(self.room.is_available(d(5), d(7)))

    def test_past_booking_cannot_be_cancelled(self):
        booking = Booking.create_booking(guest=self.guest, room=self.room, check_in=d(5), check_out=d(7))
        Booking.objects.filter(pk=booking.pk).update(check_in=d(-3), check_out=d(-1))
        self.client.force_login(self.guest)
        booking.refresh_from_db()
        response = self.client.post(reverse("booking_cancel", kwargs={"pk": booking.pk}))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)   # unchanged


class OwnerAreaTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        self.hotel = make_hotel(self.owner, "Owner Hotel")

    def test_owner_sees_only_own_hotels(self):
        make_hotel(self.other, "Others Hotel")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("manage_hotels"))
        self.assertContains(response, "Owner Hotel")
        self.assertNotContains(response, "Others Hotel")

    def test_rooms_page_is_owner_scoped(self):
        self.client.force_login(self.other)
        self.assertEqual(
            self.client.get(reverse("manage_rooms", kwargs={"slug": self.hotel.slug})).status_code, 404
        )

    def test_hotel_page_shows_availability_strip(self):
        make_room(self.hotel)
        response = self.client.get(self.hotel.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "night-strip")


class SeederTests(TestCase):
    def test_seed_demo_populates_marketplace(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Hotel.objects.count(), 4)
        self.assertGreaterEqual(Room.objects.filter(is_active=True).count(), 12)
        self.assertTrue(Booking.objects.exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
