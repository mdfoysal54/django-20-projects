"""DevJobs — domain tests (authored with the project)."""
from django.test import TestCase


class SmokeTests(TestCase):
    def test_home_responds(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
