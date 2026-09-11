from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Driver, Trip, Vehicle
from core.services import open_trip

class Command(BaseCommand):
    help = "Seed FleetNova."
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

        v, _ = Vehicle.objects.get_or_create(plate="DHK-METRO-09", defaults={"kind": "truck", "odometer": 48200})
        d, _ = Driver.objects.get_or_create(licence="DL-DHK-77", defaults={"name": "Karim Uddin"})
        if not Trip.objects.exists():
            open_trip(vehicle=v, driver=d, origin="Tejgaon yard", dest="Chittagong port", start_km=48200)
        self.stdout.write(self.style.SUCCESS("FleetNova seeded."))
