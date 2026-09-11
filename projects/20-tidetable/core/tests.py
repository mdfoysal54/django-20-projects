from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import DiningTable, Guest, MenuItem, Reservation
from .services import DomainError, book, fire_ticket

class BookingTests(TestCase):
    def setUp(self):
        self.t = DiningTable.objects.create(code="T1", seats=4)
        self.g = Guest.objects.create(name="Nadia")
        self.start = timezone.now() + timedelta(hours=2)

    def test_party_cannot_exceed_seats(self):
        with self.assertRaises(DomainError):
            book(guest=self.g, table=self.t, party_size=8, start=self.start)

    def test_window_clash(self):
        book(guest=self.g, table=self.t, party_size=2, start=self.start)
        with self.assertRaises(DomainError):
            book(guest=Guest.objects.create(name="Rafi"), table=self.t, party_size=2,
                 start=self.start + timedelta(minutes=30))

    def test_kitchen_needs_dishes(self):
        rsv = book(guest=self.g, table=self.t, party_size=2, start=self.start)
        with self.assertRaises(DomainError):
            fire_ticket(rsv, [])
        item = MenuItem.objects.create(name="Hilsa", price="890")
        fire_ticket(rsv, [(item, 2)])
        rsv.refresh_from_db()
        self.assertEqual(rsv.status, Reservation.Status.SEATED)

class ViewSeedTests(TestCase):
    def test_landing(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_dash_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(Reservation.objects.exists())
        self.assertTrue(User.objects.filter(username="alice").exists())
