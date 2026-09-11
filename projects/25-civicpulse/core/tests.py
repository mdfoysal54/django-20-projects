from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Issue, Ward
from .services import DomainError, dispatch, resolve

class CivicTests(TestCase):
    def setUp(self):
        self.w = Ward.objects.create(name="Ward 19")
        self.i = Issue.objects.create(title="Pothole", ward=self.w, reporter="Nadia")
    def test_resolve_needs_crew(self):
        with self.assertRaises(DomainError):
            resolve(self.i)
        dispatch(self.i, "Roads A")
        with self.assertRaises(DomainError):
            dispatch(self.i, "Roads B")
        resolve(self.i)
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, Issue.Status.DONE)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
