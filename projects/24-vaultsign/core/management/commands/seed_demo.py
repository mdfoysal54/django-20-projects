from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Envelope, Room, Signer
from core.services import send, sign

class Command(BaseCommand):
    help = "Seed VaultSign."
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
        room, _ = Room.objects.get_or_create(name="Board")
        if not Envelope.objects.exists():
            env = Envelope.objects.create(title="Series seed NDA", room=room, owner=alice)
            Signer.objects.create(envelope=env, name="Alice Rahman", email="alice@demo.dev")
            Signer.objects.create(envelope=env, name="Counsel", email="legal@demo.dev")
            send(env)
            sign(env, "alice@demo.dev")
        self.stdout.write(self.style.SUCCESS("VaultSign seeded."))
