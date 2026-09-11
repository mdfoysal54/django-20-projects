from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Account
from .services import DomainError, balance, credit, send, void_transfer

class PayTests(TestCase):
    def setUp(self):
        self.a = Account.objects.create(user=User.objects.create_user("a", password="x"), handle="alice")
        self.b = Account.objects.create(user=User.objects.create_user("b", password="x"), handle="bob")
        credit(self.a, 1000)
    def test_overdraft(self):
        with self.assertRaises(DomainError):
            send(src=self.a, dst=self.b, amount=5000)
    def test_self_pay(self):
        with self.assertRaises(DomainError):
            send(src=self.a, dst=self.a, amount=10)
    def test_void_restores(self):
        t = send(src=self.a, dst=self.b, amount=250)
        self.assertEqual(balance(self.a), 750)
        void_transfer(t)
        self.assertEqual(balance(self.a), 1000)
        self.assertEqual(balance(self.b), 0)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
