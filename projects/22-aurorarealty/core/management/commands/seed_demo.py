from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Agent, Listing
from core.services import book_viewing, place_offer

class Command(BaseCommand):
    help = "Seed AuroraRealty."
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

        ag, _ = Agent.objects.get_or_create(licence="REA-DHK-01", defaults={"name": "Maya Rahman"})
        if not Listing.objects.exists():
            l = Listing.objects.create(title="North Lake penthouse", suburb="Gulshan", price=42000000, beds=4, agent=ag)
            Listing.objects.create(title="River duplex", suburb="Baridhara", price=28000000, beds=3, agent=ag)
            book_viewing(l, timezone.now() + timedelta(days=2), "Nadia Karim")
            place_offer(l, "OrbitPay Ltd", 40000000)
        self.stdout.write(self.style.SUCCESS("AuroraRealty seeded."))
