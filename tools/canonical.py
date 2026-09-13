"""Canonical Python code templates shared by every flagship project.

Tokens: __SLUG__, __TITLE__, __TAG__ are substituted by scaffold.py.
"""

PROJECTS = [
    # ---- flagships (already built) ------------------------------------------
    {"dir": "01-shopnest", "title": "ShopNest", "tag": "Full-featured e-commerce platform"},
    {"dir": "02-learnhub", "title": "LearnHub", "tag": "Online learning platform (LMS)"},
    {"dir": "03-stayhub", "title": "StayHub", "tag": "Hotel & room booking engine"},
    {"dir": "04-devjobs", "title": "DevJobs", "tag": "Job board & recruitment portal"},
    {"dir": "05-taskflow", "title": "TaskFlow", "tag": "Team projects & kanban task manager"},
    {"dir": "06-fintrack", "title": "FinTrack", "tag": "Personal finance & budget dashboard"},
    # ---- second wave ---------------------------------------------------------
    {"dir": "07-blogpress", "title": "BlogPress", "tag": "Blog & publishing platform with comments"},
    {"dir": "08-eventtix", "title": "EventTix", "tag": "Event ticketing with capacity control"},
    {"dir": "09-helpdesk", "title": "HelpDesk", "tag": "Support ticket desk with agent queue"},
    {"dir": "10-medcare", "title": "MedCare", "tag": "Clinic appointment scheduling"},
    {"dir": "11-fittrack", "title": "FitTrack", "tag": "Workout & fitness progress tracker"},
    {"dir": "12-recipebox", "title": "RecipeBox", "tag": "Recipe sharing with ratings & favourites"},
    {"dir": "13-invoicepro", "title": "InvoicePro", "tag": "Freelancer invoicing & payments"},
    {"dir": "14-attendx", "title": "AttendX", "tag": "Class attendance tracking & reports"},
    {"dir": "15-quizmaster", "title": "QuizMaster", "tag": "Online quizzes with auto-grading"},
    {"dir": "16-linkshort", "title": "LinkShort", "tag": "URL shortener with click analytics"},
    # ---- wave 3: sellable operating systems ---------------------------------
    {"dir": "17-nexora", "title": "Nexora", "tag": "Retail operating system — POS, stock, purchase, accounts, warranty, installment"},
    {"dir": "18-campusos", "title": "CampusOS", "tag": "School operating system — admissions, fees, exams, timetable, parent portal"},
    {"dir": "19-aetherhr", "title": "AetherHR", "tag": "People operating system — HRIS, attendance, leave, payroll, performance"},
    # ---- wave 4: ten distinct deployable websites ---------------------------
    {"dir": "20-tidetable", "title": "TideTable", "tag": "Restaurant operating system — floor, reservations, kitchen"},
    {"dir": "21-parcelio", "title": "Parcelio", "tag": "Courier operating system — waybills, scans, COD"},
    {"dir": "22-aurorarealty", "title": "AuroraRealty", "tag": "Property operating system — listings, viewings, offers"},
    {"dir": "23-salonova", "title": "Salonova", "tag": "Salon operating system — stylists, chairs, memberships"},
    {"dir": "24-vaultsign", "title": "VaultSign", "tag": "Contract operating system — versions, parties, e-sign"},
    {"dir": "25-civicpulse", "title": "CivicPulse", "tag": "Civic operating system — wards, requests, SLA"},
    {"dir": "26-fleetnova", "title": "FleetNova", "tag": "Mobility operating system — fleet, rentals, inspections"},
    {"dir": "27-orbitpay", "title": "OrbitPay", "tag": "Wallet operating system — P2P transfers, merchant QR"},
    {"dir": "28-pulsegrid", "title": "PulseGrid", "tag": "Telemetry operating system — devices, alerts, firmware"},
    {"dir": "29-lexora", "title": "Lexora", "tag": "Practice operating system — matters, hearings, time, invoices"},
    # ---- visa / recruitment agency ERP --------------------------------------
    {"dir": "30-trustoverseas", "title": "Trust Overseas Ltd",
     "tag": "Visa & recruitment ERP — cases, GAMCA, vault, double-entry, GCC portals"},
]

# --------------------------------------------------------------------------
MANAGE = '''#!/usr/bin/env python3
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH? Did you forget to activate the "
            "virtual environment? (see README.md Quickstart)"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
'''

# --------------------------------------------------------------------------
SETTINGS = '''"""
__TITLE__ — Django settings.

Secure-by-default. Every secret, host and hardening flag is driven by
environment variables (a .env file is read automatically if present).
See docs/SECURITY.md for the full hardening checklist and README.md for the
quickstart.
"""
from pathlib import Path
import os
import secrets
import warnings

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or not raw.strip().isdigit():
        return default
    return int(raw)


# ---------------------------------------------------------------- secrets
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if env_bool("DJANGO_DEBUG", True):
        SECRET_KEY = "dev-only-" + secrets.token_hex(48)
        warnings.warn(
            "DJANGO_SECRET_KEY is not set -> using a random development key. "
            "Always set a real secret in production.",
            stacklevel=2,
        )
    else:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
ALLOWED_HOSTS.append("testserver")  # required by the test client

CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS").split(",") if o.strip()]

# ---------------------------------------------------------------- apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.SecurityHeadersMiddleware",          # CSP + nonce + extra headers
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.LoginThrottleMiddleware",            # brute-force protection
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.middleware.site_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------- database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# PostgreSQL in production?  pip install "psycopg[binary]>=3.2" then replace
# the block above with the engine + host/user/password read from environment
# variables — everything else in this file is database-agnostic.

# ---------------------------------------------------------------- passwords
# Argon2id first = state of the art; PBKDF2 kept as a fallback for legacy hashes.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------- i18n / tz
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Dhaka")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------- static/media
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------- transport security
# Flip these on when deploying behind HTTPS (see .env.example).
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
_cookies_secure = env_bool("DJANGO_COOKIE_SECURE", SECURE_SSL_REDIRECT)
_hsts = env_bool("DJANGO_HSTS", False)
SECURE_HSTS_SECONDS = 31536000 if _hsts else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _hsts
SECURE_HSTS_PRELOAD = _hsts
SESSION_COOKIE_SECURE = _cookies_secure
CSRF_COOKIE_SECURE = _cookies_secure
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("DJANGO_BEHIND_PROXY", False) else None

# ---------------------------------------------------------------- cookie hardening
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"                       # clickjacking
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7          # 7-day sessions
SESSION_SAVE_EVERY_REQUEST = False

# ---------------------------------------------------------------- auth routing
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
CSRF_FAILURE_VIEW = "core.views_errors.csrf_failure"

# ---------------------------------------------------------------- email
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DJANGO_FROM_EMAIL", "noreply@example.com")
# Production: switch EMAIL_BACKEND to smtp and read host/user/password from env.

# ---------------------------------------------------------------- app metadata
APP_NAME = "__TITLE__"
APP_TAGLINE = "__TAG__"

# ---------------------------------------------------------------- brute-force protection
AUTH_LOGIN_MAX_ATTEMPTS = env_int("DJANGO_LOGIN_MAX_ATTEMPTS", 5)
AUTH_LOGIN_WINDOW_SECONDS = env_int("DJANGO_LOGIN_WINDOW_SECONDS", 60)

# ---------------------------------------------------------------- misc hardening
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_500_000          # 2.5 MB request bodies
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
'''

# --------------------------------------------------------------------------
CONFIG_URLS = '''"""__TITLE__ — root URL configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "__TITLE__ Admin"
admin.site.site_title = "__TITLE__ administration"
admin.site.index_title = "Manage __TITLE__"

# Branded, first-party error pages (403 / 404 / 429 / 500).
handler400 = "core.views_errors.bad_request"
handler403 = "core.views_errors.permission_denied"
handler404 = "core.views_errors.page_not_found"
handler500 = "core.views_errors.server_error"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
'''

# --------------------------------------------------------------------------
WSGI = '''"""__TITLE__ — WSGI entry point."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()
'''

# --------------------------------------------------------------------------
ASGI = '''"""__TITLE__ — ASGI entry point."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
'''

# --------------------------------------------------------------------------
APPS = '''from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "__TITLE__"
'''

# --------------------------------------------------------------------------
MIDDLEWARE = '''"""__TITLE__ — hardening middleware.

1. SecurityHeadersMiddleware
   Adds a strict Content-Security-Policy with a fresh per-request nonce
   (usable in templates as {{ csp_nonce }}), plus Referrer-Policy and
   Permissions-Policy headers. The Django admin keeps its own slightly more
   permissive policy so its inline widgets keep working.
2. LoginThrottleMiddleware
   Sliding-window brute-force protection on the login form, keyed by both
   remote IP *and* submitted username. Successful logins reset the counters.
"""
from __future__ import annotations

import secrets
import threading
import time

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import Resolver404, resolve


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


class SecurityHeadersMiddleware:
    """Append security headers to every response and mint a CSP nonce."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(18)
        response = self.get_response(request)
        if "Content-Security-Policy" not in response:
            nonce = request.csp_nonce
            if request.path.startswith("/admin"):
                policy = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; font-src 'self' data:; "
                    "frame-ancestors 'none'; object-src 'none'; "
                    "base-uri 'self'; form-action 'self'"
                )
            else:
                policy = (
                    "default-src 'self'; "
                    "script-src 'self' 'nonce-%s'; "
                    "style-src 'self' 'nonce-%s'; "
                    "img-src 'self' data:; font-src 'self'; "
                    "frame-ancestors 'none'; object-src 'none'; "
                    "base-uri 'self'; form-action 'self'"
                ) % (nonce, nonce)
                if not settings.DEBUG:
                    policy += "; upgrade-insecure-requests"
            response["Content-Security-Policy"] = policy
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        response.setdefault("X-Content-Type-Options", "nosniff")
        return response


def site_processor(request):
    """Context processor: expose app metadata + CSP nonce to templates."""
    return {
        "APP_NAME": settings.APP_NAME,
        "APP_TAGLINE": settings.APP_TAGLINE,
        "csp_nonce": getattr(request, "csp_nonce", ""),
    }


# ------------------------------------------------------------------ throttling
_ATTEMPTS = {}          # key -> [timestamps]
_LOCK = threading.Lock()


def _prune(key: tuple):
    window = settings.AUTH_LOGIN_WINDOW_SECONDS
    cutoff = time.monotonic() - window
    stamps = _ATTEMPTS.get(key, [])
    _ATTEMPTS[key] = [t for t in stamps if t > cutoff]


def _blocked(key: tuple) -> bool:
    with _LOCK:
        _prune(key)
        return len(_ATTEMPTS.get(key, [])) >= settings.AUTH_LOGIN_MAX_ATTEMPTS


def _record(key: tuple) -> None:
    with _LOCK:
        _prune(key)
        _ATTEMPTS.setdefault(key, []).append(time.monotonic())


def reset_throttle() -> None:
    """Test helper / manual reset."""
    with _LOCK:
        _ATTEMPTS.clear()


def _clear(key: tuple) -> None:
    with _LOCK:
        _ATTEMPTS.pop(key, None)


@user_logged_in.connect
def _on_login_success(sender, request, user, **kwargs):
    ip = _client_ip(request)
    _clear(("ip", ip))
    _clear(("user", getattr(user, "username", "").lower()))


class LoginThrottleMiddleware:
    """429 responses after N failed login attempts (per IP and per username)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            try:
                match = resolve(request.path)
            except Resolver404:
                match = None
            if match is not None and match.url_name == "login":
                username = request.POST.get("username", "").lower()
                keys = [("ip", _client_ip(request))]
                if username:
                    keys.append(("user", username))
                if any(_blocked(k) for k in keys):
                    attempts = settings.AUTH_LOGIN_MAX_ATTEMPTS
                    window = settings.AUTH_LOGIN_WINDOW_SECONDS
                    body = render_to_string(
                        "errors/429.html",
                        {"attempts": attempts, "window_seconds": window},
                        request=request,
                    )
                    return HttpResponse(body, status=429)
                for k in keys:
                    _record(k)
        return self.get_response(request)
'''

# --------------------------------------------------------------------------
AUTH_VIEWS = '''"""__TITLE__ — registration views (login/logout live in core.urls)."""
from django.contrib import messages
from django.contrib.auth import login
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic.edit import FormView


class RegisterForm(UserCreationForm):
    """Username + email + strong password. Email is unique and required."""

    email = forms.EmailField(required=True, label="Email address")

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "Pick a username (letters, digits, @ . + - _)",
            "email": "you@example.com",
            "password1": "8+ characters, not all numbers, not too common",
            "password2": "Repeat the password",
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["placeholder"] = placeholders.get(name, "")


class RegisterView(FormView):
    """Create the account and log the user straight in."""

    form_class = RegisterForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Welcome! Your account was created.")
        return super().form_valid(form)
'''

# --------------------------------------------------------------------------
MODELS_STUB = '''"""__TITLE__ — data models (authored with the project's domain logic)."""

# Models for this flagship project are defined here. See the project README
# for the domain spec. This file is replaced when the project is built out.
'''

FORMS_STUB = '''"""__TITLE__ — domain forms (authored with the project)."""
'''

ADMIN_STUB = '''"""__TITLE__ — admin registrations (authored with the project)."""
'''

VIEWS_STUB = '''"""__TITLE__ — views (authored with the project)."""
from django.shortcuts import render


def index(request):
    return render(request, "construction.html", {"page_title": "__TITLE__"})
'''

VIEWS_ERRORS = '''"""__TITLE__ — branded error handlers (400/403/404/429/500 + CSRF)."""
import logging

from django.shortcuts import render

logger = logging.getLogger(__name__)


def page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", status=403)


def bad_request(request, exception=None):
    return render(request, "errors/400.html", status=400)


def server_error(request):
    return render(request, "errors/500.html", status=500)


def csrf_failure(request, reason=""):
    logger.warning("Rejected request with invalid CSRF token: %s", reason)
    return render(request, "errors/403.html", {"reason": reason}, status=403)
'''

CORE_URLS = '''"""__TITLE__ — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from .auth_views import RegisterView
from .views import index

urlpatterns = [
    path("", index, name="home"),
    # ---- accounts -----------------------------------------------------
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="done",
        ),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
'''

# --------------------------------------------------------------------------
TESTS_STUB = '''"""__TITLE__ — domain tests (authored with the project)."""
from django.test import TestCase


class SmokeTests(TestCase):
    def test_home_responds(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
'''

TESTS_SECURITY = '''"""Canonical security test-suite — identical for every flagship project.

Covers: security headers + CSP nonce, CSRF presence on forms, registration,
login flow and brute-force throttling on the login endpoint.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .middleware import reset_throttle


class SecurityHeaderTests(TestCase):
    def setUp(self):
        reset_throttle()

    def test_csp_and_hardening_headers_present(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self' 'nonce-", csp)      # nonce minted per request
        self.assertIn("style-src 'self' 'nonce-", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertEqual(response.headers.get("Referrer-Policy"), "same-origin")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

    def test_csp_nonce_unique_per_request(self):
        r1 = self.client.get(reverse("login")).headers["Content-Security-Policy"]
        r2 = self.client.get(reverse("login")).headers["Content-Security-Policy"]
        self.assertNotEqual(r1, r2)

    def test_login_form_has_csrf_token(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_admin_keeps_usable_csp(self):
        response = self.client.get("/admin/login/")
        csp = response.headers.get("Content-Security-Policy", "")
        self.assertIn("'unsafe-inline'", csp)   # admin widgets require it


class RegistrationTests(TestCase):
    def setUp(self):
        reset_throttle()

    def test_register_then_login_redirects_home(self):
        response = self.client.post(reverse("register"), {
            "username": "alice",
            "email": "alice@example.com",
            "password1": "Str0ng!Passw0rd",
            "password2": "Str0ng!Passw0rd",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 1)
        self.assertIn("_auth_user_id", self.client.session)

    def test_duplicate_email_rejected(self):
        User.objects.create_user("bob", email="bob@example.com", password="x-Passw0rd!")
        response = self.client.post(reverse("register"), {
            "username": "bob2",
            "email": "bob@example.com",
            "password1": "Str0ng!Passw0rd",
            "password2": "Str0ng!Passw0rd",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_weak_password_rejected(self):
        response = self.client.post(reverse("register"), {
            "username": "carol",
            "email": "carol@example.com",
            "password1": "password",
            "password2": "password",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)


class LoginThrottleTests(TestCase):
    def setUp(self):
        reset_throttle()
        self.password = "Str0ng!Passw0rd"
        User.objects.create_user("mallory", email="m@example.com", password=self.password)
        self.login_url = reverse("login")

    def _post_login(self, username, password):
        return self.client.post(self.login_url, {"username": username, "password": password})

    def test_allows_max_attempts_then_blocks(self):
        for _ in range(5):
            response = self._post_login("mallory", "wrong-pass")
            self.assertEqual(response.status_code, 200)     # form re-rendered
        response = self._post_login("mallory", "wrong-pass")
        self.assertEqual(response.status_code, 429)         # throttled
        self.assertContains(response, "Too many", status_code=429)

    def test_correct_password_also_blocked_while_throttled(self):
        for _ in range(6):
            self._post_login("mallory", "wrong-pass")
        response = self._post_login("mallory", self.password)
        self.assertEqual(response.status_code, 429)

    @override_settings(AUTH_LOGIN_MAX_ATTEMPTS=2)
    def test_brute_force_keyed_per_username_and_ip(self):
        # Keys are (ip, ...) AND (username, ...) — blocking on either one.
        # This means a username-rotation attack from one IP still runs out of
        # attempts (the shared IP budget), while a fresh IP gets its own run.
        User.objects.create_user("eve", email="eve@example.com", password=self.password)
        User.objects.create_user("frank", email="frank@example.com", password=self.password)

        # mallory exhausts both budgets from this IP (2 wrong attempts).
        self.assertEqual(self._post_login("mallory", "wrong").status_code, 200)
        self.assertEqual(self._post_login("mallory", "wrong").status_code, 200)
        # Username budget spent -> blocked.
        self.assertEqual(self._post_login("mallory", "wrong").status_code, 429)
        # eve on the SAME IP is blocked too (shared per-IP budget, by design:
        # stops an attacker rotating usernames from one machine).
        self.assertEqual(self._post_login("eve", "wrong").status_code, 429)

        # frank from a DIFFERENT IP has clean budgets -> gets his own 2 tries.
        fresh_ip_client = self.client_class(HTTP_X_FORWARDED_FOR="203.0.113.77")
        response = fresh_ip_client.post(
            self.login_url, {"username": "frank", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        response = fresh_ip_client.post(
            self.login_url, {"username": "frank", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        response = fresh_ip_client.post(
            self.login_url, {"username": "frank", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 429)

    def test_successful_login_resets_throttle(self):
        for _ in range(6):
            self._post_login("mallory", "wrong-pass")
        reset_throttle()
        response = self._post_login("mallory", self.password)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
'''

# --------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    for p in PROJECTS:
        print(p["dir"], "-", p["title"])
