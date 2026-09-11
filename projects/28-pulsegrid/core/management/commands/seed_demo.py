from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Incident, Monitor, OnCall, Site
from core.services import page_incident

class Command(BaseCommand):
    help = "Seed PulseGrid."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):

        if not settings.DEBUG and not options["force"]:
            self.stderr.write("Refusing to seed with DEBUG=False.")
            return
        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@demo.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()
        alice, created = User.objects.get_or_create(username="alice",
            defaults={"first_name": "Alice", "last_name": "Rahman", "email": "alice@demo.dev"})
        if created:
            alice.set_password("DemoPass123!")
            alice.save()

        s, _ = Site.objects.get_or_create(slug="edge", defaults={"name": "edge-dhaka"})
        OnCall.objects.get_or_create(site=s, defaults={"name": "Alice Rahman"})
        m, _ = Monitor.objects.get_or_create(site=s, name="https")
        if not Incident.objects.exists():
            page_incident(monitor=m, title="TLS handshake spike", severity="sev2")
        self.stdout.write(self.style.SUCCESS("PulseGrid seeded."))
