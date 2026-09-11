from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Issue, Ward
from core.services import dispatch

class Command(BaseCommand):
    help = "Seed CivicPulse."
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

        w, _ = Ward.objects.get_or_create(name="Ward 19")
        Ward.objects.get_or_create(name="Ward 27")
        if not Issue.objects.exists():
            i = Issue.objects.create(title="Open manhole, Road 11", ward=w, category="safety", reporter="Nadia Karim")
            dispatch(i, "Public Works North", "Barricade tonight")
        self.stdout.write(self.style.SUCCESS("CivicPulse seeded."))
