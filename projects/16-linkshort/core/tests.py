"""LinkShort domain tests — redirect safety, click accounting, privacy, ownership."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Click, ShortLink, normalise_target


def make_link(owner, target="https://example.com/landing", **kw):
    return ShortLink.objects.create(owner=owner, target_url=target, **kw)


class URLSafetyTests(TestCase):
    def test_https_and_http_are_allowed(self):
        self.assertEqual(normalise_target("https://example.com"), "https://example.com")
        self.assertEqual(normalise_target("http://example.com/x?y=1"), "http://example.com/x?y=1")

    def test_bare_domain_gets_https(self):
        self.assertEqual(normalise_target("example.com/page"), "https://example.com/page")

    def test_javascript_and_data_urls_are_refused(self):
        for bad in ("javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=", "vbscript:msgbox(1)"):
            with self.assertRaises(ValidationError):
                normalise_target(bad)

    def test_ftp_and_file_schemes_are_refused(self):
        for bad in ("ftp://example.com/file", "file:///etc/passwd"):
            with self.assertRaises(ValidationError):
                normalise_target(bad)

    def test_nonsense_domains_are_refused(self):
        for bad in ("", "   ", "not a url", "https://nodot"):
            with self.assertRaises(ValidationError):
                normalise_target(bad)

    def test_form_rejects_a_javascript_url(self):
        user = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.client.force_login(user)
        response = self.client.post(reverse("link_create"), {"target_url": "javascript:alert(1)"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShortLink.objects.exists())

    @override_settings(ALLOWED_HOSTS=["testserver", "links.example.com"])
    def test_form_refuses_a_self_referential_loop(self):
        user = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.client.force_login(user)
        # A short link pointing back at our own domain would loop forever.
        response = self.client.post(reverse("link_create"), {"target_url": "https://links.example.com/s/ABC123/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "points back at LinkShort")
        self.assertFalse(ShortLink.objects.exists())


class CodeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")

    def test_codes_are_generated_and_readable(self):
        link = make_link(self.owner)
        self.assertEqual(len(link.code), 6)
        self.assertTrue(all(ch in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for ch in link.code))

    def test_codes_do_not_collide(self):
        codes = {make_link(self.owner).code for _ in range(25)}
        self.assertEqual(len(codes), 25)

    def test_generator_retries_on_a_collision(self):
        existing = make_link(self.owner)
        # Force the generator to hand back the same code twice, then a fresh one.
        with mock.patch("core.models.secrets.choice", side_effect=list(existing.code) + list("ZZZZZZ")):
            link = make_link(self.owner)
        self.assertNotEqual(link.code, existing.code)
        self.assertEqual(link.code, "ZZZZZZ")

    def test_code_is_unique_at_the_database_level(self):
        link = make_link(self.owner)
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ShortLink.objects.create(owner=self.owner, code=link.code, target_url="https://example.org")


class RedirectTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.link = make_link(self.owner, title="Launch")

    def test_redirects_to_the_target(self):
        response = self.client.get(self.link.short_path())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.link.target_url)

    def test_click_is_counted_and_recorded(self):
        with mock.patch("core.models.Click.client_ip", return_value="203.0.113.9"):
            self.client.get(self.link.short_path(), HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)")
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 1)
        click = self.link.clicks.get()
        self.assertEqual(click.device, Click.Device.MOBILE)
        self.assertTrue(click.ip_hash)
        self.assertNotIn("203.0.113.9", click.ip_hash)          # the raw IP is never stored

    def test_counter_uses_an_atomic_increment(self):
        for _ in range(3):
            self.client.get(self.link.short_path())
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 3)
        self.assertEqual(self.link.clicks.count(), 3)

    def test_unknown_code_is_404(self):
        self.assertEqual(self.client.get(reverse("redirect_link", kwargs={"code": "NOPE23"})).status_code, 404)

    def test_disabled_link_returns_410_and_does_not_count(self):
        self.link.active = False
        self.link.save(update_fields=["active"])
        response = self.client.get(self.link.short_path())
        self.assertEqual(response.status_code, 410)
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 0)

    def test_expired_link_returns_410(self):
        ShortLink.objects.filter(pk=self.link.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        self.link.refresh_from_db()
        self.assertTrue(self.link.is_expired)
        self.assertEqual(self.client.get(self.link.short_path()).status_code, 410)

    def test_capped_link_stops_redirecting(self):
        ShortLink.objects.filter(pk=self.link.pk).update(max_clicks=2)
        self.link.refresh_from_db()
        self.assertEqual(self.client.get(self.link.short_path()).status_code, 302)
        self.assertEqual(self.client.get(self.link.short_path()).status_code, 302)
        response = self.client.get(self.link.short_path())
        self.assertEqual(response.status_code, 410)
        self.link.refresh_from_db()
        self.assertEqual(self.link.click_count, 2)                # cap respected exactly

    def test_preview_page_shows_the_destination(self):
        response = self.client.get(reverse("link_preview", kwargs={"code": self.link.code}))
        self.assertContains(response, self.link.target_url)


class AnalyticsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.link = make_link(self.owner)

    def test_referrer_is_reduced_to_the_host(self):
        self.client.get(self.link.short_path(),
                        HTTP_REFERER="https://news.example.com/story?utm_source=x&user=42")
        click = self.link.clicks.get()
        self.assertEqual(click.referrer, "news.example.com")
        self.assertNotIn("user=42", click.referrer)

    def test_device_detection(self):
        cases = [
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", Click.Device.DESKTOP),
            ("Mozilla/5.0 (iPad; CPU OS 17_0)", Click.Device.TABLET),
            ("Googlebot/2.1 (+http://www.google.com/bot.html)", Click.Device.BOT),
            ("curl/8.4.0", Click.Device.BOT),
            ("", Click.Device.UNKNOWN),
        ]
        for ua, expected in cases:
            self.assertEqual(Click.detect_device(ua), expected, ua)

    def test_unique_visitors_use_the_ip_hash(self):
        with mock.patch("core.models.Click.client_ip", return_value="198.51.100.7"):
            for _ in range(3):
                self.client.get(self.link.short_path())
        with mock.patch("core.models.Click.client_ip", return_value="198.51.100.8"):
            self.client.get(self.link.short_path())
        self.link.refresh_from_db()          # the view counted on its own instance
        stats = self.link.analytics()
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["unique"], 2)

    def test_clicks_by_day_covers_the_whole_window(self):
        self.client.get(self.link.short_path())
        series = self.link.clicks_by_day(days=7)
        self.assertEqual(len(series), 7)
        self.assertEqual(sum(row["count"] for row in series), 1)
        self.assertEqual(series[-1]["date"], timezone.localdate())

    def test_analytics_page_is_owner_scoped(self):
        intruder = User.objects.create_user("intruder", password="Str0ng!Passw0rd")
        self.client.force_login(intruder)
        response = self.client.get(reverse("analytics"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.link.code)
        # ...and the per-link page simply does not exist for them.
        self.assertEqual(self.client.get(self.link.get_absolute_url()).status_code, 404)


class OwnershipTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.intruder = User.objects.create_user("intruder", password="Str0ng!Passw0rd")
        self.link = make_link(self.owner)

    def test_anonymous_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_intruder_gets_404_on_every_management_view(self):
        self.client.force_login(self.intruder)
        for name in ("link_detail", "link_edit"):
            self.assertEqual(self.client.get(reverse(name, kwargs={"code": self.link.code})).status_code, 404)
        for name in ("link_toggle", "link_delete"):
            self.assertEqual(self.client.post(reverse(name, kwargs={"code": self.link.code})).status_code, 404)
        self.assertTrue(ShortLink.objects.filter(pk=self.link.pk).exists())

    def test_owner_can_disable_and_delete(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("link_toggle", kwargs={"code": self.link.code}))
        self.link.refresh_from_db()
        self.assertFalse(self.link.active)
        self.client.post(reverse("link_delete", kwargs={"code": self.link.code}))
        self.assertFalse(ShortLink.objects.filter(pk=self.link.pk).exists())

    def test_deleting_a_link_removes_its_clicks(self):
        self.client.get(self.link.short_path())
        self.assertEqual(Click.objects.count(), 1)
        self.client.force_login(self.owner)
        self.client.post(reverse("link_delete", kwargs={"code": self.link.code}))
        self.assertEqual(Click.objects.count(), 0)

    def test_quick_shorten_creates_a_link(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("quick_shorten"), {"target_url": "example.org/offer"})
        link = ShortLink.objects.get(target_url="https://example.org/offer")
        self.assertEqual(link.owner, self.owner)

    def test_quick_shorten_refuses_dangerous_urls(self):
        self.client.force_login(self.owner)
        before = ShortLink.objects.count()
        self.client.post(reverse("quick_shorten"), {"target_url": "javascript:alert(1)"})
        self.assertEqual(ShortLink.objects.count(), before)


class SeederTests(TestCase):
    def test_seed_demo_populates_links_and_clicks(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(ShortLink.objects.count(), 6)
        self.assertTrue(Click.objects.exists())
        self.assertTrue(ShortLink.objects.filter(active=False).exists())
        self.assertTrue(Click.objects.exclude(referrer="").exists())
        # Click counters must agree with the stored click rows.
        for link in ShortLink.objects.all():
            self.assertEqual(link.click_count, link.clicks.count())
