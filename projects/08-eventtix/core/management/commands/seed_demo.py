"""Seed EventTix with organisers, events, tiers, bookings and check-ins."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Booking, Event, TicketTier

EVENTS = [
    ("dhaka-sound-festival", "Dhaka Sound Festival", "Bangabandhu International Arena", 30, "🎶",
     "Two nights, twelve bands, one very loud weekend. Gates open at 5pm.",
     [("Early bird", "45.00", 60, 0), ("General", "65.00", 240, 1), ("Front stage", "120.00", 80, 2)]),
    ("startup-dhaka-2026", "Startup Dhaka 2026", "ICCB Hall 2", 45, "🚀",
     "Founders, funders and 40 demo booths. Pitch competition on day two.",
     [("Standard", "25.00", 300, 0), ("Founder pass", "90.00", 60, 1)]),
    ("jazz-in-the-courtyard", "Jazz in the Courtyard", "Bengal Shilpalay Courtyard", 12, "🎷",
     "An intimate evening of live jazz under the stars. Seating is limited.",
     [("Seated", "35.00", 90, 0)]),
    ("devopsconf-asia", "DevOpsConf Asia", "Le Méridien Ballroom", 60, "🛠️",
     "Two tracks, hands-on workshops, and the flakiest CI pipelines in Asia.",
     [("Workshop + conf", "150.00", 70, 0), ("Conference only", "75.00", 200, 1)]),
    ("charity-5k-run", "Riverside Charity 5K", "Hatirjheel Riverside", 20, "🏃",
     "Run the loop, raise money for clean water projects. Every entry plants a tree.",
     [("Runner entry", "15.00", 400, 0), ("Family (4 runners)", "50.00", 40, 1)]),
]


class Command(BaseCommand):
    help = "Create demo organisers, events, tiers and bookings."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for username, staff in [("priya", False), ("omar", False), ("sara", False), ("admin", True)]:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"email": f"{username}@eventtix.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = user.is_superuser = True
            user.save()

        organisers = [User.objects.get(username=u) for u in ("priya", "omar", "sara")]
        buyers = [User.objects.get(username=u) for u in ("omar", "sara", "priya")]
        now = timezone.now()

        for i, (slug, title, venue, days, emoji, description, tiers) in enumerate(EVENTS):
            organiser = organisers[i % len(organisers)]
            event, created = Event.objects.get_or_create(
                slug=slug,
                defaults={"organiser": organiser, "title": title, "venue": venue,
                          "starts_at": now + timedelta(days=days),
                          "ends_at": now + timedelta(days=days, hours=4),
                          "cover_emoji": emoji, "description": description, "status": Event.Status.ON_SALE},
            )
            if not created:
                continue
            for name, price, capacity, order in tiers:
                TicketTier.objects.create(event=event, name=name, price=Decimal(price),
                                          capacity=capacity, order=order)

            # A handful of realistic bookings, some partially checked in.
            for j, buyer in enumerate(buyers[: (i % 3) + 1]):
                tier = event.tiers.order_by("order")[j % event.tiers.count()]
                booking, _ = Booking.create_booking(buyer, event, tier, (j % 3) + 1)
                if booking and j == 0:
                    Booking.objects.filter(pk=booking.pk).update(checked_in=min(1, booking.quantity))

            if i == len(EVENTS) - 1:
                # A cancelled booking to demo refunds in the UI.
                tier = event.tiers.order_by("order").first()
                booking, _ = Booking.create_booking(buyers[0], event, tier, 1)
                if booking:
                    booking.cancel()

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Event.objects.count()} events, {TicketTier.objects.count()} tiers, "
            f"{Booking.objects.count()} bookings."
        ))
