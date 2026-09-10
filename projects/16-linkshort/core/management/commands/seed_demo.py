"""Seed LinkShort with demo links and a realistic spread of clicks."""
import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Click, ShortLink

LINKS = [
    ("Launch announcement — v3.0", "https://example.com/blog/linkshort-3-0-launch",
     "marketing, launch", "🗞️", True, None),
    ("Q3 pricing page", "https://example.com/pricing?utm_source=newsletter&utm_campaign=q3",
     "marketing", "💳", True, None),
    ("Engineering hiring post", "https://example.com/careers/backend-engineer-dhaka",
     "hiring", "🧑‍💻", True, None),
    ("Webinar recording", "https://videos.example.org/watch/linkshort-analytics-deep-dive",
     "content, webinar", "🎥", True, None),
    ("Black Friday landing page", "https://shop.example.com/black-friday",
     "campaign", "🛍️", False, None),          # disabled on purpose
    ("Old referral program", "https://example.com/referral/2025",
     "legacy", "📦", True, 3),                 # capped after three clicks
    ("Support docs — short links", "https://docs.example.com/guides/short-links",
     "docs", "📚", True, None),
    ("Conference talk slides", "https://slides.example.com/django-analytics-deck",
     "content, conference", "🖼️", True, None),
]

REFERRERS = ["news.example.com", "t.co", "mail.google.com", "linkedin.com", "facebook.com", "reddit.com"]
AGENTS = [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "desktop"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15", "desktop"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) Mobile/15E148", "mobile"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36", "mobile"),
    ("Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X)", "tablet"),
    ("Googlebot/2.1 (+http://www.google.com/bot.html)", "bot"),
]


class Command(BaseCommand):
    help = "Create demo short links with click history."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        rng = random.Random(1609)
        today = timezone.now()

        owner, created = User.objects.get_or_create(
            username="marketer", defaults={"first_name": "Farhana", "last_name": "Islam",
                                           "email": "farhana@linkshort.dev"})
        if created:
            owner.set_password("DemoPass123!")
            owner.save()

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@linkshort.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        for title, target, tags, _emoji, active, cap in LINKS:
            if ShortLink.objects.filter(target_url=target).exists():
                continue
            link = ShortLink.objects.create(owner=owner, title=title, target_url=target, tags=tags,
                                            active=active, max_clicks=cap)
            # Backdate creation a little so "recent" charts have range.
            ShortLink.objects.filter(pk=link.pk).update(created=today - timedelta(days=rng.randint(6, 30)))

            clicks = rng.randint(4, 40)
            if not active:
                clicks = rng.randint(0, 4)
            if cap:
                clicks = min(clicks, cap)
            for i in range(clicks):
                agent, device = rng.choice(AGENTS)
                ip = f"203.0.113.{rng.randint(1, 60)}"
                created_at = today - timedelta(days=rng.randint(0, 13), hours=rng.randint(0, 23),
                                               minutes=rng.randint(0, 59))
                click = Click.objects.create(
                    link=link,
                    referrer=rng.choice(REFERRERS) if rng.random() > 0.25 else "",
                    user_agent=agent,
                    ip_hash=Click.hash_ip(ip),
                    device=device,
                )
                Click.objects.filter(pk=click.pk).update(created=created_at)
            ShortLink.objects.filter(pk=link.pk).update(click_count=clicks)

        self.stdout.write(self.style.SUCCESS(
            f"Done: {ShortLink.objects.count()} links, {Click.objects.count()} clicks "
            f"({ShortLink.objects.aggregate(n=__import__('django.db.models', fromlist=['Sum']).Sum('click_count'))['n']} counted)."
        ))
