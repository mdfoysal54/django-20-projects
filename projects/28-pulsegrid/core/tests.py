from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Monitor, Site
from .services import DomainError, ack, page_incident, resolve

class GridTests(TestCase):
    def setUp(self):
        s = Site.objects.create(name="api", slug="api")
        self.m = Monitor.objects.create(site=s, name="latency")
    def test_dedupe(self):
        page_incident(monitor=self.m, title="p99")
        with self.assertRaises(DomainError):
            page_incident(monitor=self.m, title="p99")
    def test_ack_then_resolve(self):
        inc = page_incident(monitor=self.m, title="5xx")
        ack(inc)
        with self.assertRaises(DomainError):
            ack(inc)
        resolve(inc)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
