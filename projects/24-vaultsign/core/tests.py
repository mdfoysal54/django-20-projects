from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Envelope, Room, Signer
from .services import DomainError, send, sign, void

class SignTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("maya", password="x")
        self.room = Room.objects.create(name="Legal")
        self.env = Envelope.objects.create(title="NDA", room=self.room, owner=self.u)
        Signer.objects.create(envelope=self.env, name="Alice", email="alice@demo.dev")
    def test_send_needs_signer(self):
        empty = Envelope.objects.create(title="Empty", room=self.room, owner=self.u)
        with self.assertRaises(DomainError):
            send(empty)
        send(self.env)
        sign(self.env, "alice@demo.dev")
        self.env.refresh_from_db()
        self.assertEqual(self.env.status, Envelope.Status.SIGNED)
        with self.assertRaises(DomainError):
            void(self.env)
    def test_unknown_email(self):
        send(self.env)
        with self.assertRaises(DomainError):
            sign(self.env, "nobody@x.dev")
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
