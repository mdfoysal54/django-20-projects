from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Courier, Station
from .services import DomainError, advance, intake

class ParcelTests(TestCase):
    def setUp(self):
        self.st = Station.objects.create(name="Gulshan Hub", city="Dhaka")
        self.c = Courier.objects.create(name="Rafi", station=self.st)
    def test_weight_cap(self):
        with self.assertRaises(DomainError):
            intake(sender="A", recipient="B", dest_city="Chittagong", weight_kg=40, origin=self.st)
    def test_needs_courier(self):
        p = intake(sender="A", recipient="B", dest_city="Sylhet", weight_kg=2, origin=self.st)
        p = advance(p)
        with self.assertRaises(DomainError):
            advance(p)
        advance(p, courier=self.c)
        self.assertEqual(p.status, "out")
    def test_no_reopen(self):
        p = intake(sender="A", recipient="B", dest_city="Sylhet", weight_kg=1, origin=self.st)
        p.status = "done"; p.save()
        with self.assertRaises(DomainError):
            advance(p)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
