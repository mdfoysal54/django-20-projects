"""LinkShort models — short codes, safe targets and privacy-conscious click analytics."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

#: Unambiguous alphabet (no I/O/0/1) so codes survive being read aloud or typed.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6

#: Schemes we will never redirect to. javascript:/data: are XSS vectors.
BLOCKED_SCHEMES = ("javascript", "data", "vbscript", "file", "ftp")


def normalise_target(raw: str) -> str:
    """Validate and normalise a destination URL, raising ValidationError if unsafe."""
    value = (raw or "").strip()
    if not value:
        raise ValidationError("Enter a destination URL.")
    if "://" not in value:
        value = "https://" + value
    parts = urlsplit(value)
    if parts.scheme.lower() in BLOCKED_SCHEMES:
        raise ValidationError(f"“{parts.scheme}:” links are not allowed.")
    if parts.scheme.lower() not in ("http", "https"):
        raise ValidationError("Only http and https links can be shortened.")
    if not parts.netloc or "." not in parts.netloc.split(":")[0]:
        raise ValidationError("That does not look like a valid domain.")
    return value


class ShortLink(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="links")
    code = models.CharField(max_length=12, unique=True, editable=False, db_index=True)
    target_url = models.URLField(max_length=500, help_text="Where the short link sends visitors.")
    title = models.CharField(max_length=120, blank=True)
    tags = models.CharField(max_length=120, blank=True, help_text="Optional comma-separated tags.")
    created = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    max_clicks = models.PositiveIntegerField(null=True, blank=True,
                                             help_text="Stop redirecting after this many clicks.")
    active = models.BooleanField(default=True)
    click_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["owner", "-created"])]

    def __str__(self):
        return f"{self.code} → {self.target_url[:60]}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._new_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _new_code(length=CODE_LENGTH) -> str:
        while True:
            code = "".join(secrets.choice(ALPHABET) for _ in range(length))
            if not ShortLink.objects.filter(code=code).exists():
                return code

    def get_absolute_url(self):
        return reverse("link_detail", kwargs={"code": self.code})

    def short_path(self) -> str:
        return reverse("redirect_link", kwargs={"code": self.code})

    # ------------------------------------------------------------- link health
    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_capped(self) -> bool:
        return self.max_clicks is not None and self.click_count >= self.max_clicks

    @property
    def can_redirect(self) -> bool:
        return self.active and not self.is_expired and not self.is_capped

    def status_label(self) -> str:
        if not self.active:
            return "disabled"
        if self.is_expired:
            return "expired"
        if self.is_capped:
            return "capped"
        return "active"

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    # ----------------------------------------------------------------- clicks
    @transaction.atomic
    def register_click(self, request=None):
        """Record one click atomically — the counter is incremented in SQL, never read-modify-write."""
        ShortLink.objects.filter(pk=self.pk).update(click_count=models.F("click_count") + 1)
        self.refresh_from_db(fields=["click_count"])
        return Click.objects.create(
            link=self,
            referrer=Click.clean_referrer(request.META.get("HTTP_REFERER", "") if request else ""),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else "")[:300],
            ip_hash=Click.hash_ip(Click.client_ip(request) if request else ""),
            device=Click.detect_device(request.META.get("HTTP_USER_AGENT", "") if request else ""),
        )

    def clicks_by_day(self, days=14):
        """Clicks per day for the last `days` days, newest last (chart-ready)."""
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)
        counts = {start + timedelta(days=i): 0 for i in range(days)}
        for click in self.clicks.filter(created__date__gte=start):
            day = timezone.localtime(click.created).date()
            if day in counts:
                counts[day] += 1
        return [{"date": day, "count": n} for day, n in sorted(counts.items())]

    def analytics(self):
        clicks = self.clicks.all()
        unique_visitors = clicks.values("ip_hash").distinct().count()
        devices = {row["device"]: row["n"] for row in clicks.values("device").annotate(n=models.Count("id"))}
        top_referrers = (clicks.exclude(referrer="")
                         .values("referrer").annotate(n=models.Count("id")).order_by("-n")[:5])
        return {
            "total": self.click_count,
            "unique": unique_visitors,
            "today": clicks.filter(created__date=timezone.localdate()).count(),
            "last_7": clicks.filter(created__gte=timezone.now() - timedelta(days=7)).count(),
            "devices": devices,
            "top_referrers": list(top_referrers),
            "first_click": clicks.order_by("created").first(),
            "last_click": clicks.order_by("-created").first(),
        }


class Click(models.Model):
    class Device(models.TextChoices):
        DESKTOP = "desktop", "Desktop"
        MOBILE = "mobile", "Mobile"
        TABLET = "tablet", "Tablet"
        BOT = "bot", "Bot"
        UNKNOWN = "unknown", "Unknown"

    link = models.ForeignKey(ShortLink, on_delete=models.CASCADE, related_name="clicks")
    created = models.DateTimeField(auto_now_add=True)
    referrer = models.CharField(max_length=300, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    #: We store a salted hash of the IP, never the address itself.
    ip_hash = models.CharField(max_length=64, blank=True)
    device = models.CharField(max_length=8, choices=Device.choices, default=Device.UNKNOWN)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["link", "-created"])]

    def __str__(self):
        return f"click on {self.link.code}"

    # -------------------------------------------------------------- privacy
    @staticmethod
    def client_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")

    @staticmethod
    def hash_ip(ip: str) -> str:
        if not ip:
            return ""
        salt = str(settings.SECRET_KEY)
        return hashlib.sha256(f"linkshort:{salt}:{ip}".encode()).hexdigest()[:40]

    @staticmethod
    def clean_referrer(referrer: str) -> str:
        """Keep the host of the referrer only — no query strings, no full paths."""
        if not referrer:
            return ""
        parts = urlsplit(referrer)
        return (parts.netloc or referrer)[:300]

    @staticmethod
    def detect_device(user_agent: str) -> str:
        ua = (user_agent or "").lower()
        if not ua:
            return Click.Device.UNKNOWN
        for bot in ("bot", "crawler", "spider", "curl", "wget", "python-requests", "headless"):
            if bot in ua:
                return Click.Device.BOT
        if "ipad" in ua or ("tablet" in ua and "mobile" not in ua):
            return Click.Device.TABLET
        if any(token in ua for token in ("mobile", "iphone", "android", "phone")):
            return Click.Device.MOBILE
        return Click.Device.DESKTOP


class DailyRollup(models.Model):
    """Optional nightly aggregate so long-lived links stay fast to chart."""

    link = models.ForeignKey(ShortLink, on_delete=models.CASCADE, related_name="rollups")
    date = models.DateField()
    clicks = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["link", "date"], name="one_rollup_per_link_per_day")]

    def __str__(self):
        return f"{self.link.code} {self.date}: {self.clicks}"
