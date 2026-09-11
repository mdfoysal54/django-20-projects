from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Courier, Parcel, Station
from core.services import advance, intake

class Command(BaseCommand):
    help = "Seed Parcelio."
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

        st, _ = Station.objects.get_or_create(name="Gulshan Hub", defaults={"city": "Dhaka"})
        Station.objects.get_or_create(name="Agrabad", defaults={"city": "Chittagong"})
        c, _ = Courier.objects.get_or_create(name="Rafi Hasan", defaults={"station": st})
        if not Parcel.objects.exists():
            p = intake(sender="Nexora Ltd", recipient="CampusOS", dest_city="Sylhet", weight_kg=2.4, origin=st, cod=450)
            advance(p); advance(p, courier=c)
        self.stdout.write(self.style.SUCCESS("Parcelio seeded."))
