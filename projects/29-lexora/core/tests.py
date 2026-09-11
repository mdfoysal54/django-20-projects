from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Matter
from .services import DomainError, bill, log_time

class LexTests(TestCase):
    def setUp(self):
        self.m = Matter.objects.create(title="Share sale", client="Nexora", rate=6000, retainer=10000)
    def test_min_slice(self):
        with self.assertRaises(DomainError):
            log_time(self.m, 3, "call")
    def test_bill(self):
        log_time(self.m, 60, "draft")
        inv = bill(self.m)
        self.assertEqual(inv.amount, 6000)
        with self.assertRaises(DomainError):
            bill(self.m)
    def test_closed(self):
        self.m.status = Matter.Status.CLOSE
        self.m.save()
        with self.assertRaises(DomainError):
            log_time(self.m, 30, "x")
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
