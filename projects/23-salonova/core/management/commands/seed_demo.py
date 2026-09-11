from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Appointment, Client, Service, Stylist
from core.services import book

class Command(BaseCommand):
    help = "Seed Salonova."
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

        s, _ = Stylist.objects.get_or_create(name="Lina Noor")
        Stylist.objects.get_or_create(name="Rafi Cut")
        svc, _ = Service.objects.get_or_create(name="Signature cut", defaults={"minutes": 45, "price": 1400})
        Service.objects.get_or_create(name="Colour gloss", defaults={"minutes": 90, "price": 3200})
        c, _ = Client.objects.get_or_create(name="Nadia Karim")
        if not Appointment.objects.exists():
            book(client=c, stylist=s, service=svc, start=timezone.now() + timedelta(hours=4))
        self.stdout.write(self.style.SUCCESS("Salonova seeded."))
