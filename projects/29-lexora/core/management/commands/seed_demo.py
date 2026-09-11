from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Matter
from core.services import bill, log_time

class Command(BaseCommand):
    help = "Seed Lexora."
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

        if not Matter.objects.exists():
            m = Matter.objects.create(title="Series seed round", client="OrbitPay Ltd", rate=9000, retainer=50000)
            log_time(m, 90, "term sheet markup")
            bill(m)
        self.stdout.write(self.style.SUCCESS("Lexora seeded."))
