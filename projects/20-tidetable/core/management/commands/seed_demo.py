from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import DiningTable, Guest, MenuItem, Venue
from core.services import book, fire_ticket

class Command(BaseCommand):
    help = "Seed TideTable."
    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
    def handle(self, *args, **options):

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

        Venue.get()
        for code, seats, zone in (("T1", 2, "Window"), ("T2", 4, "Main"), ("T3", 6, "Garden"), ("T4", 4, "Main")):
            DiningTable.objects.get_or_create(code=code, defaults={"seats": seats, "zone": zone})
        for name, price, course in (("Hilsa bhuna", "890", "mains"), ("Beef tehari", "420", "mains"),
                                    ("Pithas", "180", "dessert"), ("Borhani", "90", "drinks")):
            MenuItem.objects.get_or_create(name=name, defaults={"price": price, "course": course})
        g, _ = Guest.objects.get_or_create(name="Nadia Karim", defaults={"phone": "0172"})
        from core.models import Reservation
        if not Reservation.objects.exists():
            rsv = book(guest=g, table=DiningTable.objects.get(code="T2"), party_size=3,
                       start=timezone.now() + timedelta(hours=3))
            fire_ticket(rsv, [(MenuItem.objects.first(), 2)])
        self.stdout.write(self.style.SUCCESS("TideTable seeded."))
