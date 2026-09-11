from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Agent, Listing, Offer
from .services import DomainError, accept_offer, book_viewing, place_offer

class RealtyTests(TestCase):
    def setUp(self):
        self.a = Agent.objects.create(name="Maya", licence="REA-1")
        self.l = Listing.objects.create(title="Lakeview", suburb="Gulshan", price=20000000, beds=3, agent=self.a)
    def test_lowball(self):
        with self.assertRaises(DomainError):
            place_offer(self.l, "Buyer", 1000000)
    def test_accept_closes_others(self):
        o1 = place_offer(self.l, "A", 18000000)
        o2 = place_offer(self.l, "B", 19000000)
        accept_offer(o2)
        o1.refresh_from_db(); self.l.refresh_from_db()
        self.assertEqual(o1.status, Offer.Status.LOSE)
        self.assertEqual(self.l.status, Listing.Status.SOLD)
        with self.assertRaises(DomainError):
            book_viewing(self.l, timezone.now() + timedelta(days=1), "X")
    def test_past_viewing(self):
        with self.assertRaises(DomainError):
            book_viewing(self.l, timezone.now() - timedelta(days=1), "X")
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
