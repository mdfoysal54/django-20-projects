"""Seed StayHub with demo hotels, rooms, guests and bookings."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Booking, Hotel, Room

HOTELS = [
    {
        "name": "The Riverside Grand", "city": "Dhaka", "stars": 5, "emoji": "🏨",
        "amenities": "Free WiFi, Infinity pool, Spa, Rooftop bar, Airport shuttle",
        "description": "A five-star landmark on the Buriganga with panoramic city views, "
                       "three restaurants and a full-service spa.",
        "rooms": [
            ("501", Room.RoomType.SUITE, 3, "185.00", "Corner suite with river view and lounge area."),
            ("401", Room.RoomType.DOUBLE, 2, "95.00", "King bed, rain shower, city view."),
            ("402", Room.RoomType.TWIN, 2, "85.00", "Two singles — great for colleagues."),
            ("305", Room.RoomType.SINGLE, 1, "60.00", "Compact solo room with workspace."),
        ],
    },
    {
        "name": "Palm Cove Resort", "city": "Cox's Bazar", "stars": 4, "emoji": "🌴",
        "amenities": "Free WiFi, Beach access, Outdoor pool, Breakfast included",
        "description": "Beachfront resort steps from the world's longest natural sea beach. "
                       "Every room has a balcony; most face the Bay of Bengal.",
        "rooms": [
            ("201", Room.RoomType.FAMILY, 5, "140.00", "Two bedrooms, kitchenette, sea-facing balcony."),
            ("112", Room.RoomType.DOUBLE, 2, "78.00", "Partial sea view, queen bed."),
            ("108", Room.RoomType.TWIN, 2, "70.00", "Garden view, two singles."),
        ],
    },
    {
        "name": "Hilltop Tea Retreat", "city": "Sylhet", "stars": 4, "emoji": "🍃",
        "amenities": "Free WiFi, Guided tea tours, Fireplace lounge, Restaurant",
        "description": "A serene retreat among the tea gardens of Sylhet with sunrise "
                       "views over the valley and legendary breakfast parathas.",
        "rooms": [
            ("A2", Room.RoomType.SUITE, 3, "120.00", "Private terrace overlooking the tea estate."),
            ("A1", Room.RoomType.DOUBLE, 2, "80.00", "Wood-panelled room with valley view."),
            ("B1", Room.RoomType.SINGLE, 1, "55.00", "Cosy solo room with reading nook."),
        ],
    },
    {
        "name": "Urban Loft Chattogram", "city": "Chattogram", "stars": 3, "emoji": "🏙️",
        "amenities": "Free WiFi, Coworking lounge, 24h gym, Laundry",
        "description": "Smart, compact lofts designed for business travellers — walk to the "
                       "port district, work from the coworking lounge, gym at midnight if you like.",
        "rooms": [
            ("701", Room.RoomType.DOUBLE, 2, "65.00", "High-floor loft with desk and smart TV."),
            ("702", Room.RoomType.TWIN, 2, "68.00", "Twin loft for colleagues."),
            ("703", Room.RoomType.FAMILY, 4, "99.00", "Two-zone loft with bunk nook."),
        ],
    },
]


class Command(BaseCommand):
    help = "Create demo hosts, hotels, rooms, guests and a few bookings."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        host, created = User.objects.get_or_create(
            username="host", defaults={"email": "host@stayhub.dev"})
        if created:
            host.set_password("DemoPass123!")
        host.save()
        admin, created = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@stayhub.dev"})
        if created:
            admin.set_password("DemoPass123!")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        for spec in HOTELS:
            hotel, created = Hotel.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "owner": host, "city": spec["city"], "star_rating": spec["stars"],
                    "hero_emoji": spec["emoji"], "amenities": spec["amenities"],
                    "description": spec["description"],
                    "address": f"{spec['city']} city centre",
                },
            )
            if created:
                for number, rtype, cap, price, blurb in spec["rooms"]:
                    Room.objects.create(
                        hotel=hotel, number=number, room_type=rtype,
                        capacity=cap, price_per_night=Decimal(price), description=blurb,
                    )

        # Demo guests
        guests = []
        for username in ("alice", "bob"):
            user, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"})
            if created:
                user.set_password("DemoPass123!")
                user.save()
            guests.append(user)

        # A booking that exists, and one in the past (for history views)
        today = timezone.localdate()
        first_room = Room.objects.order_by("pk").first()
        if first_room and not Booking.objects.filter(guest=guests[0]).exists():
            Booking.create_booking(
                guest=guests[0], room=first_room,
                check_in=today + timedelta(days=6), check_out=today + timedelta(days=9),
                guests=2, special_requests="Late check-in around 11 pm, please.",
            )
        second_room = Room.objects.order_by("-pk").first()
        if second_room and not Booking.objects.filter(guest=guests[1]).exists():
            booking = Booking.create_booking(
                guest=guests[1], room=second_room,
                check_in=today + timedelta(days=2), check_out=today + timedelta(days=4),
                guests=1,
            )
            Booking.objects.filter(pk=booking.pk).update(
                check_in=today - timedelta(days=30), check_out=today - timedelta(days=28),
                status=Booking.Status.COMPLETED,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Hotel.objects.count()} hotels, {Room.objects.count()} rooms, "
            f"{Booking.objects.count()} bookings."
        ))
