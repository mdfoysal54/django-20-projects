from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Driver, Vehicle
from .services import DomainError, close_trip, open_trip

class FleetTests(TestCase):
    def setUp(self):
        self.v = Vehicle.objects.create(plate="DHK-101", odometer=1000)
        self.d = Driver.objects.create(name="Karim", licence="DL-1")
    def test_double_dispatch(self):
        open_trip(vehicle=self.v, driver=self.d, origin="A", dest="B", start_km=1000)
        with self.assertRaises(DomainError):
            open_trip(vehicle=self.v, driver=Driver.objects.create(name="B", licence="DL-2"),
                      origin="A", dest="C", start_km=1000)
    def test_rewind(self):
        t = open_trip(vehicle=self.v, driver=self.d, origin="A", dest="B", start_km=1000)
        with self.assertRaises(DomainError):
            close_trip(t, 800)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
