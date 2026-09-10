"""EventTix domain tests — capacity control, cancellation refunds, check-in."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, BookingLine, Event, TicketTier


def make_event(organiser, capacity=10, price="25.00", status=Event.Status.ON_SALE,
               slug="dhaka-sound", **kw):
    event = Event.objects.create(
        organiser=organiser, title="Dhaka Sound Festival", slug=slug,
        venue="Bangabandhu Arena", starts_at=timezone.now() + timedelta(days=30),
        status=status, **kw,
    )
    tier = TicketTier.objects.create(event=event, name="General", price=Decimal(price), capacity=capacity)
    return event, tier


class CapacityTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user("organiser", password="Str0ng!Passw0rd")
        self.buyer = User.objects.create_user("buyer", password="Str0ng!Passw0rd")
        self.event, self.tier = make_event(self.organiser, capacity=5)

    def test_booking_decrements_remaining(self):
        booking, err = Booking.create_booking(self.buyer, self.event, self.tier, 2)
        self.assertIsNone(err)
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.sold, 2)
        self.assertEqual(self.tier.remaining, 3)
        self.assertEqual(booking.quantity, 2)
        self.assertEqual(booking.total, Decimal("50.00"))
        self.assertTrue(booking.reference.startswith("ET-"))

    def test_cannot_oversell_last_seats(self):
        Booking.create_booking(self.buyer, self.event, self.tier, 4)
        booking, err = Booking.create_booking(self.buyer, self.event, self.tier, 3)
        self.assertIsNone(booking)
        self.assertIn("Only 1 ticket", err)
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.sold, 4)          # nothing leaked

    def test_sold_out_event_flips_status(self):
        Booking.create_booking(self.buyer, self.event, self.tier, 5)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.SOLD_OUT)
        booking, err = Booking.create_booking(self.buyer, self.event, self.tier, 1)
        self.assertIsNone(booking)

    def test_db_constraint_blocks_manual_oversell(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TicketTier.objects.filter(pk=self.tier.pk).update(sold=99)

    def test_zero_quantity_rejected(self):
        booking, err = Booking.create_booking(self.buyer, self.event, self.tier, 0)
        self.assertIsNone(booking)
        self.assertIn("at least one", err.lower())

    def test_draft_event_cannot_be_booked(self):
        draft, tier = make_event(self.organiser, status=Event.Status.DRAFT, slug="draft-ev")
        booking, err = Booking.create_booking(self.buyer, draft, tier, 1)
        self.assertIsNone(booking)
        self.assertIn("not on sale", err)


class CancellationTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user("organiser", password="Str0ng!Passw0rd")
        self.buyer = User.objects.create_user("buyer", password="Str0ng!Passw0rd")
        self.event, self.tier = make_event(self.organiser, capacity=3)

    def test_cancel_returns_seats_and_reopens_event(self):
        booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 3)
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, Event.Status.SOLD_OUT)

        self.assertTrue(booking.cancel())
        self.tier.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.tier.sold, 0)
        self.assertEqual(self.event.status, Event.Status.ON_SALE)
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)

    def test_double_cancel_is_a_noop(self):
        booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 2)
        self.assertTrue(booking.cancel())
        self.assertFalse(booking.cancel())           # idempotent
        self.tier.refresh_from_db()
        self.assertEqual(self.tier.sold, 0)          # never goes negative

    def test_buyer_can_cancel_own_booking_via_view(self):
        booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 1)
        self.client.force_login(self.buyer)
        response = self.client.post(reverse("booking_cancel", kwargs={"reference": booking.reference}))
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_stranger_cannot_cancel_someone_elses_booking(self):
        booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 1)
        stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.client.force_login(stranger)
        response = self.client.post(reverse("booking_cancel", kwargs={"reference": booking.reference}))
        self.assertEqual(response.status_code, 404)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_booking_confirmation_hidden_from_strangers(self):
        booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 1)
        stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.client.force_login(stranger)
        response = self.client.get(reverse("booking_detail", kwargs={"reference": booking.reference}))
        self.assertEqual(response.status_code, 404)


class CheckInTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user("organiser", password="Str0ng!Passw0rd")
        self.buyer = User.objects.create_user("buyer", password="Str0ng!Passw0rd")
        self.event, self.tier = make_event(self.organiser, capacity=4)
        self.booking, _ = Booking.create_booking(self.buyer, self.event, self.tier, 2)

    def test_organiser_scans_until_quantity_reached(self):
        self.client.force_login(self.organiser)
        url = reverse("door_check_in", kwargs={"slug": self.event.slug, "reference": self.booking.reference})
        self.client.post(url)
        self.client.post(url)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.checked_in, 2)

    def test_check_in_stops_at_quantity(self):
        self.client.force_login(self.organiser)
        url = reverse("door_check_in", kwargs={"slug": self.event.slug, "reference": self.booking.reference})
        self.client.post(url)
        self.client.post(url)
        response = self.client.post(url, follow=True)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.checked_in, 2)   # third scan does nothing
        self.assertContains(response, "already been checked in")

    def test_stranger_cannot_check_in(self):
        stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.client.force_login(stranger)
        response = self.client.post(reverse("door_check_in", kwargs={"slug": self.event.slug, "reference": self.booking.reference}))
        self.assertEqual(response.status_code, 404)


class OrganiserScopeTests(TestCase):
    def setUp(self):
        self.organiser = User.objects.create_user("organiser", password="Str0ng!Passw0rd")
        self.rival = User.objects.create_user("rival", password="Str0ng!Passw0rd")
        self.event, self.tier = make_event(self.organiser)

    def test_only_organiser_sees_attendee_list(self):
        self.client.force_login(self.rival)
        response = self.client.get(reverse("event_attendees", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 404)
        self.client.force_login(self.organiser)
        response = self.client.get(reverse("event_attendees", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)

    def test_public_event_page_shows_availability(self):
        response = self.client.get(self.event.get_absolute_url())
        self.assertContains(response, "10")            # capacity visible
        self.assertEqual(response.status_code, 200)


class SeederTests(TestCase):
    def test_seed_demo_populates_events(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Event.objects.count(), 4)
        self.assertTrue(TicketTier.objects.exists())
        self.assertTrue(Booking.objects.exists())
        self.assertTrue(BookingLine.objects.exists())
        self.assertTrue(Booking.objects.filter(status=Booking.Status.CANCELLED).exists())
