from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Account, Transfer
from core.services import credit, send

class Command(BaseCommand):
    help = "Seed OrbitPay."
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

        alice = User.objects.get(username="alice")
        admin = User.objects.get(username="admin")
        aa, _ = Account.objects.get_or_create(user=alice, defaults={"handle": "alice"})
        ab, _ = Account.objects.get_or_create(user=admin, defaults={"handle": "orbit"})
        if not Transfer.objects.exists():
            credit(aa, 50000, "genesis")
            send(src=aa, dst=ab, amount=1200, memo="demo")
        self.stdout.write(self.style.SUCCESS("OrbitPay seeded."))
