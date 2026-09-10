"""Seed ShopNest with demo catalogue, users and a sample order.

Usage:  python manage.py seed_demo [--force]
The command refuses to run when DEBUG=False unless --force is passed.
"""
import struct
import zlib
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Cart, CartItem, Category, Order, Product

CATALOGUE = [
    # (category, icon, name, price, stock, featured, blurb)
    ("Electronics", "🔌", "Aurora Wireless Headphones", "89.99", 14, True, "Over-ear ANC headphones with 40h battery and deep-bass tuning."),
    ("Electronics", "🔌", "Pulse Smart Watch S2", "149.50", 8, True, "Heart-rate, GPS and sleep tracking in a 1.4in AMOLED body."),
    ("Electronics", "🔌", "Nimbus USB-C Hub 7-in-1", "39.00", 40, False, "Seven ports: 4K HDMI, 3× USB 3.0, 100W PD passthrough."),
    ("Electronics", "🔌", "Volt 20,000mAh Power Bank", "32.75", 25, False, "Fast 45W two-way charging with LED capacity display."),
    ("Fashion", "👕", "Everyday Organic Tee", "19.99", 60, False, "100% combed organic cotton, pre-shrunk, six colours."),
    ("Fashion", "👕", "Trailblazer Denim Jacket", "74.00", 12, True, "Classic indigo denim with a soft brushed interior."),
    ("Fashion", "👕", "Urban Canvas Backpack", "49.90", 18, False, "15in laptop sleeve, waterproof base, reflective trim."),
    ("Books", "📚", "The Pragmatic Developer", "27.99", 30, True, "Timeless lessons on clean code, testing and career craft."),
    ("Books", "📚", "Designing Data-Intensive Systems", "54.50", 9, False, "The modern classic on distributed systems architecture."),
    ("Home & Living", "🛋️", "Lumen Smart LED Lamp", "45.00", 16, False, "Warm-to-cool white, app & voice control, sleep timer."),
    ("Sports", "⚽", "AeroFit Yoga Mat 6mm", "28.00", 22, False, "Non-slip dual-layer TPE with carry strap."),
    ("Beauty", "🧴", "Glow Daily Moisturiser SPF30", "21.50", 35, False, "Lightweight hydration with broad-spectrum sun defence."),
]

# Gradient palettes per category (hex pairs) used to render demo images.
PALETTES = {
    "Electronics": ("#312e81", "#6d5ae0"),
    "Fashion": ("#9f1239", "#e0698d"),
    "Books": ("#92400e", "#e8a13d"),
    "Home & Living": ("#0f766e", "#4dd0bd"),
    "Sports": ("#166534", "#57c98a"),
    "Beauty": ("#831843", "#e86fc0"),
}


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def make_gradient_png(path: Path, hex1: str, hex2: str, width: int = 640, height: int = 800) -> None:
    """Write a soft vertical-gradient PNG (no Pillow required)."""
    def parse(hx: str):
        return [int(hx[i:i + 2], 16) for i in (1, 3, 5)]

    c1, c2 = parse(hex1), parse(hex2)
    raw = bytearray()
    for y in range(height):
        t = y / (height - 1)
        rgb = bytes(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        raw += b"\x00" + rgb * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class Command(BaseCommand):
    help = "Create demo categories, products (with generated images), users and a sample order."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR(
                "Refusing to seed demo data with DEBUG=False. Pass --force to override."
            ))
            return

        media = Path(settings.MEDIA_ROOT)
        for category_name, icon, name, price, stock, featured, blurb in CATALOGUE:
            category, _ = Category.objects.get_or_create(
                name=category_name, defaults={"icon": icon, "description": f"{category_name} at {settings.APP_NAME}."}
            )
            product, created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": Decimal(price),
                    "stock": int(stock),
                    "status": Product.Status.PUBLISHED,
                    "featured": bool(featured),
                    "description": blurb,
                },
            )
            if created and not product.image:
                file_name = f"{product.slug}.png"
                make_gradient_png(media / "products" / file_name, *PALETTES[category_name])
                product.image = f"products/{file_name}"
                product.save(update_fields=["image"])

        # Demo users: admin / admin — alice / DemoPass123!
        admin, _ = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True, "email": "admin@shopnest.dev"}
        )
        if not admin.has_usable_password():
            admin.set_password("admin")
            admin.save()
        alice, created = User.objects.get_or_create(
            username="alice", defaults={"email": "alice@example.com"}
        )
        if created:
            alice.set_password("DemoPass123!")
            alice.save()

        # Sample order for alice so her order history is not empty.
        if not alice.orders.exists():
            cart, _ = Cart.objects.get_or_create(user=alice)
            picks = list(Product.objects.filter(status=Product.Status.PUBLISHED, stock__gte=2)[:3])
            for product in picks:
                CartItem.objects.create(cart=cart, product=product, quantity=2)
            try:
                order = Order.create_from_cart(
                    cart,
                    shipping_address="House 12, Road 5, Dhanmondi",
                    city="Dhaka",
                    phone="+8801700000000",
                )
                order.created = timezone.now() - timezone.timedelta(days=2)
                order.save(update_fields=["created"])
                self.stdout.write(self.style.SUCCESS(f"Sample order {order.number} created for alice."))
            except ValueError:
                pass

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Category.objects.count()} categories, {Product.objects.count()} products, "
            f"{User.objects.count()} users."
        ))
