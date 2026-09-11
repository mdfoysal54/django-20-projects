from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Client, Service, Stylist
from .services import DomainError, book

class SalonTests(TestCase):
    def setUp(self):
        self.s = Stylist.objects.create(name="Lina")
        self.svc = Service.objects.create(name="Cut", minutes=45, price=1200)
        self.c = Client.objects.create(name="Nadia")
        self.t = timezone.now() + timedelta(hours=2)
    def test_overlap(self):
        book(client=self.c, stylist=self.s, service=self.svc, start=self.t)
        with self.assertRaises(DomainError):
            book(client=Client.objects.create(name="Rafi"), stylist=self.s, service=self.svc,
                 start=self.t + timedelta(minutes=10))
    def test_past(self):
        with self.assertRaises(DomainError):
            book(client=self.c, stylist=self.s, service=self.svc, start=timezone.now() - timedelta(hours=2))
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
