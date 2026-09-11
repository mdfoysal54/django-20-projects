#!/usr/bin/env python3
"""Build wave-4 flagship projects (20–29) on top of the scaffold."""
from __future__ import annotations

import pathlib
import shutil
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSS_BODY = (ROOT / "projects/19-aetherhr/static/css/style.css").read_text(encoding="utf-8")
# drop the AetherHR-specific :root header; keep layout from first `* {`
IDX = CSS_BODY.find("* { box-sizing")
LAYOUT = CSS_BODY[IDX:] if IDX >= 0 else CSS_BODY


def w(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n") if content.startswith("\n") else content, encoding="utf-8")


def css(vars_block: str) -> str:
    return f"/* first-party stylesheet — no CDN */\n:root {{\n{vars_block}\n}}\n" + LAYOUT


def base_html(title: str, badge: str, cta_url: str, cta: str, footer: str) -> str:
    return f"""{{% load static %}}
<!doctype html>
<html lang="en" data-theme="{{ ui_theme|default:'void' }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{% block title %}}{title}{{% endblock %}} · {{{{ APP_NAME }}}}</title>
<meta name="description" content="{{{{ APP_TAGLINE }}}}">
<meta name="color-scheme" content="dark light">
<link rel="stylesheet" href="{{% static 'css/style.css' %}}">
</head>
<body class="{{% if user.is_authenticated %}}app-shell{{% endif %}}">
{{% if user.is_authenticated %}}
<aside class="rail">
  <a class="brand" href="{{% url 'dashboard' %}}"><span class="brand-badge">{badge}</span><span>{title}</span></a>
  {{% for group, items in nav %}}
    <div class="rail-group">{{{{ group }}}}</div>
    {{% for name, label in items %}}
      <a class="nav-item{{% if request.resolver_match.url_name == name %}} active{{% endif %}}" href="{{% url name %}}">{{{{ label }}}}</a>
    {{% endfor %}}
  {{% empty %}}
    <a class="nav-item" href="{{% url 'dashboard' %}}">Dashboard</a>
  {{% endfor %}}
</aside>
{{% endif %}}
<div class="{{% if user.is_authenticated %}}stage{{% endif %}}">
  {{% if user.is_authenticated %}}
  <header class="topbar">
    <div class="small muted">{{% block crumb %}}{{{{ APP_TAGLINE }}}}{{% endblock %}}</div>
    <div class="nav-right">
      <a class="btn btn-sm btn-primary" href="{{% url '{cta_url}' %}}">{cta}</a>
      <a class="btn btn-sm btn-ghost" href="{{% url 'profile' %}}">{{{{ user.username }}}}</a>
      <form method="post" action="{{% url 'logout' %}}">{{% csrf_token %}}
        <button class="btn btn-sm btn-secondary" type="submit">Log out</button>
      </form>
    </div>
  </header>
  {{% endif %}}
  <main class="{{% if user.is_authenticated %}}stage-main{{% else %}}landing-main{{% endif %}}">
    {{% if messages %}}{{% for message in messages %}}
      <div class="alert alert-{{{{ message.tags|default:'info' }}}}" role="status">{{{{ message }}}}</div>
    {{% endfor %}}{{% endif %}}
    {{% block content %}}{{% endblock %}}
  </main>
  {{% if user.is_authenticated %}}
  <footer class="site-footer">© {{% now "Y" %}} {{{{ APP_NAME }}}} — {footer}</footer>
  {{% endif %}}
</div>
</body>
</html>
"""


def page(title: str, body: str) -> str:
    return f"""{{% extends "base.html" %}}
{{% block title %}}{title}{{% endblock %}}
{{% block content %}}
{body}
{{% endblock %}}
"""


AUTH_URLS = '''
    path("profile/", views.profile, name="profile"),
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
'''


def urls(header: str, extra: str) -> str:
    return f'''"""{header} URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
{extra}
{AUTH_URLS}
'''


def readme(title: str, tag: str, rules: str) -> str:
    return f"""# {title}

> **{tag}** — flagship Django project in the **django-20-projects** monorepo.

A complete, deployable product: first-party UI, hardened Django 5.2, Argon2, CSP + nonce, tests, demo seeder. No CDN, no secrets in git.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
```

Demo: `alice` / `DemoPass123!`  ·  admin: `admin` / `admin`

## Domain rules

{rules}

Django 5.2 LTS · WhiteNoise · SQLite / PostgreSQL-ready · `check --deploy` clean.
"""


def seed_users() -> str:
    return '''
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
'''


def profile_view() -> str:
    return '''
@login_required
def profile(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("first_name") or u.first_name
        u.email = request.POST.get("email") or u.email
        u.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "account/profile.html", _ctx(request))
'''


PROFILE_TMPL = page("Profile", """
<div class="card"><h1>Profile</h1>
<form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">First name</label>
    <input class="form-control" name="first_name" value="{{ user.first_name }}"></div>
  <div class="form-group"><label class="form-label">Email</label>
    <input class="form-control" name="email" value="{{ user.email }}"></div>
  <button class="btn btn-primary" type="submit">Save</button>
</form>
<p class="mt-2"><a href="{% url 'password_change' %}">Change password</a></p></div>
""")


def landing(kicker, h1, lede, cards) -> str:
    cards_html = "\n".join(
        f'<div class="card"><h3>{t}</h3><p class="muted">{d}</p></div>' for t, d in cards
    )
    return page("Home", f"""
<div class="hero-block">
  <div class="kicker">{kicker}</div>
  <h1>{h1}</h1>
  <p class="lede">{lede}</p>
  <p><a class="btn btn-primary btn-lg" href="{{% url 'login' %}}">Open the desk</a>
     <a class="btn btn-secondary btn-lg" href="{{% url 'register' %}}">Create an account</a></p>
</div>
<div class="feature-grid">
{cards_html}
</div>
""")


# ===================================================================== projects

def build_tidetable(base: pathlib.Path) -> None:
    w(base / "core/models.py", '''
"""TideTable — restaurant floor, reservations, kitchen."""
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

def money(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class Venue(models.Model):
    name = models.CharField(max_length=120, default="Tide Table")
    theme = models.CharField(max_length=16, default="ember")
    @classmethod
    def get(cls):
        o, _ = cls.objects.get_or_create(pk=1)
        return o
    def __str__(self):
        return self.name

class DiningTable(models.Model):
    code = models.CharField(max_length=8, unique=True)
    seats = models.PositiveSmallIntegerField()
    zone = models.CharField(max_length=40, default="Main")
    def __str__(self):
        return f"{self.code} ({self.seats})"

class Guest(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=24, blank=True)
    def __str__(self):
        return self.name

class Reservation(models.Model):
    class Status(models.TextChoices):
        BOOKED = "book", "Booked"
        SEATED = "seat", "Seated"
        DONE = "done", "Completed"
        NO_SHOW = "ns", "No-show"
        CX = "cx", "Cancelled"
    number = models.CharField(max_length=20, unique=True, editable=False)
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="reservations")
    table = models.ForeignKey(DiningTable, on_delete=models.PROTECT, related_name="reservations")
    party_size = models.PositiveSmallIntegerField()
    start = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.BOOKED)
    note = models.CharField(max_length=200, blank=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%Y%m%d")
            n = Reservation.objects.filter(number__startswith=f"RSV-{day}").count() + 1
            self.number = f"RSV-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("reservation_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class MenuItem(models.Model):
    name = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    course = models.CharField(max_length=20, default="mains")
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class Ticket(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name="tickets")
    sent_at = models.DateTimeField(auto_now_add=True)
    fired = models.BooleanField(default=False)

class TicketLine(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    qty = models.PositiveSmallIntegerField(default=1)
''')
    w(base / "core/services.py", '''
"""TideTable domain."""
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from .models import Reservation, Ticket, TicketLine

class DomainError(ValueError):
    pass

WINDOW = timedelta(minutes=90)

@transaction.atomic
def book(*, guest, table, party_size, start, note=""):
    if party_size < 1:
        raise DomainError("Party size must be at least 1.")
    if party_size > table.seats:
        raise DomainError(f"{table.code} only seats {table.seats}.")
    clash = Reservation.objects.filter(table=table, status__in=(Reservation.Status.BOOKED, Reservation.Status.SEATED)).filter(
        start__lt=start + WINDOW, start__gt=start - WINDOW)
    if clash.exists():
        raise DomainError("That table is already reserved in this window.")
    return Reservation.objects.create(guest=guest, table=table, party_size=party_size, start=start, note=note)

@transaction.atomic
def fire_ticket(reservation, items):
    if reservation.status == Reservation.Status.CX:
        raise DomainError("Cancelled covers cannot go to the kitchen.")
    if not items:
        raise DomainError("Add at least one dish.")
    ticket = Ticket.objects.create(reservation=reservation, fired=True)
    for item, qty in items:
        TicketLine.objects.create(ticket=ticket, item=item, qty=qty)
    reservation.status = Reservation.Status.SEATED
    reservation.save(update_fields=["status"])
    return ticket
''')
    w(base / "core/views.py", '''
"""TideTable views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import DiningTable, Guest, MenuItem, Reservation, Venue
from .services import DomainError, book, fire_ticket

NAV = [("Floor", [("dashboard", "Board"), ("reservation_list", "Reservations"), ("table_list", "Tables")]),
       ("Kitchen", [("kitchen", "Tickets"), ("menu_list", "Menu")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    extra.setdefault("venue", Venue.get())
    extra.setdefault("today", timezone.localdate())
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    today = timezone.localdate()
    rows = Reservation.objects.filter(start__date=today).select_related("guest", "table")
    return render(request, "app/dashboard.html", _ctx(request, rows=rows,
        n_booked=rows.filter(status="book").count(), n_seated=rows.filter(status="seat").count(),
        n_tables=DiningTable.objects.count()))

@login_required
def reservation_list(request):
    return render(request, "app/list.html", _ctx(request, title="Reservations",
        rows=Reservation.objects.select_related("guest", "table").order_by("-start")[:80], kind="rsv"))

@login_required
def reservation_detail(request, number):
    rsv = get_object_or_404(Reservation, number=number)
    if request.method == "POST":
        try:
            items = []
            for item in MenuItem.objects.filter(is_active=True):
                raw = request.POST.get(f"q_{item.pk}", "").strip()
                if raw and int(raw) > 0:
                    items.append((item, int(raw)))
            fire_ticket(rsv, items)
            messages.success(request, "Kitchen ticket fired.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(rsv)
    return render(request, "app/detail.html", _ctx(request, rsv=rsv, menu=MenuItem.objects.filter(is_active=True), kind="rsv"))

@login_required
def reservation_new(request):
    if request.method == "POST":
        try:
            guest, _ = Guest.objects.get_or_create(name=request.POST.get("name") or "Guest",
                                                   defaults={"phone": request.POST.get("phone") or ""})
            table = get_object_or_404(DiningTable, pk=request.POST.get("table"))
            start = parse_datetime(request.POST.get("start") or "") or timezone.now()
            if timezone.is_naive(start):
                start = timezone.make_aware(start)
            rsv = book(guest=guest, table=table, party_size=int(request.POST.get("party") or 2), start=start)
            messages.success(request, f"{rsv.number} booked.")
            return redirect(rsv)
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, title="New reservation",
        tables=DiningTable.objects.all(), kind="rsv"))

@login_required
def table_list(request):
    return render(request, "app/list.html", _ctx(request, title="Floor plan",
        rows=DiningTable.objects.all(), kind="tbl"))

@login_required
def menu_list(request):
    return render(request, "app/list.html", _ctx(request, title="Menu",
        rows=MenuItem.objects.all(), kind="menu"))

@login_required
def kitchen(request):
    from .models import Ticket
    tickets = Ticket.objects.select_related("reservation__table").order_by("-sent_at")[:40]
    return render(request, "app/kitchen.html", _ctx(request, tickets=tickets))
''' + profile_view())
    w(base / "core/urls.py", urls("TideTable", '''
    path("reservations/", views.reservation_list, name="reservation_list"),
    path("reservations/new/", views.reservation_new, name="reservation_new"),
    path("reservations/<str:number>/", views.reservation_detail, name="reservation_detail"),
    path("tables/", views.table_list, name="table_list"),
    path("menu/", views.menu_list, name="menu_list"),
    path("kitchen/", views.kitchen, name="kitchen"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\n\\nfor m in (models.Venue, models.DiningTable, models.Guest, models.Reservation, models.MenuItem, models.Ticket, models.TicketLine):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import DiningTable, Guest, MenuItem, Reservation
from .services import DomainError, book, fire_ticket

class BookingTests(TestCase):
    def setUp(self):
        self.t = DiningTable.objects.create(code="T1", seats=4)
        self.g = Guest.objects.create(name="Nadia")
        self.start = timezone.now() + timedelta(hours=2)

    def test_party_cannot_exceed_seats(self):
        with self.assertRaises(DomainError):
            book(guest=self.g, table=self.t, party_size=8, start=self.start)

    def test_window_clash(self):
        book(guest=self.g, table=self.t, party_size=2, start=self.start)
        with self.assertRaises(DomainError):
            book(guest=Guest.objects.create(name="Rafi"), table=self.t, party_size=2,
                 start=self.start + timedelta(minutes=30))

    def test_kitchen_needs_dishes(self):
        rsv = book(guest=self.g, table=self.t, party_size=2, start=self.start)
        with self.assertRaises(DomainError):
            fire_ticket(rsv, [])
        item = MenuItem.objects.create(name="Hilsa", price="890")
        fire_ticket(rsv, [(item, 2)])
        rsv.refresh_from_db()
        self.assertEqual(rsv.status, Reservation.Status.SEATED)

class ViewSeedTests(TestCase):
    def test_landing(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_dash_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(Reservation.objects.exists())
        self.assertTrue(User.objects.filter(username="alice").exists())
''')
    w(base / "core/management/commands/seed_demo.py", f'''
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import DiningTable, Guest, MenuItem, Venue
from core.services import book, fire_ticket

class Command(BaseCommand):
    help = "Seed TideTable."
    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")
    def handle(self, *args, **options):
{seed_users()}
        Venue.get()
        for code, seats, zone in (("T1", 2, "Window"), ("T2", 4, "Main"), ("T3", 6, "Garden"), ("T4", 4, "Main")):
            DiningTable.objects.get_or_create(code=code, defaults={{"seats": seats, "zone": zone}})
        for name, price, course in (("Hilsa bhuna", "890", "mains"), ("Beef tehari", "420", "mains"),
                                    ("Pithas", "180", "dessert"), ("Borhani", "90", "drinks")):
            MenuItem.objects.get_or_create(name=name, defaults={{"price": price, "course": course}})
        g, _ = Guest.objects.get_or_create(name="Nadia Karim", defaults={{"phone": "0172"}})
        from core.models import Reservation
        if not Reservation.objects.exists():
            rsv = book(guest=g, table=DiningTable.objects.get(code="T2"), party_size=3,
                       start=timezone.now() + timedelta(hours=3))
            fire_ticket(rsv, [(MenuItem.objects.first(), 2)])
        self.stdout.write(self.style.SUCCESS("TideTable seeded."))
''')
    # templates
    (base / "templates/app").mkdir(parents=True, exist_ok=True)
    (base / "templates/account").mkdir(parents=True, exist_ok=True)
    w(base / "templates/base.html", base_html("TideTable", "T", "kitchen", "Kitchen", "the service, plated."))
    w(base / "templates/app/landing.html", landing("Restaurant OS",
        "Reservations, the floor and the pass — in one <em>ember</em> desk.",
        "TideTable keeps covers honest: a four-top never takes six, and two parties never share a 90-minute window.",
        [("Floor", "Tables, zones, covers."), ("Book", "Party size vs seats."), ("Kitchen", "Tickets fire from the reservation."), ("No-show", "Statuses you can actually trust.")]))
    w(base / "templates/app/dashboard.html", page("Board", """
<div class="page-head"><h1>{{ venue.name }} tonight</h1><a class="btn btn-primary" href="{% url 'reservation_new' %}">New cover</a></div>
<div class="grid grid-3">
  <div class="card stat"><div class="stat-label">Booked</div><div class="stat-value">{{ n_booked }}</div></div>
  <div class="card stat"><div class="stat-label">Seated</div><div class="stat-value">{{ n_seated }}</div></div>
  <div class="card stat"><div class="stat-label">Tables</div><div class="stat-value">{{ n_tables }}</div></div>
</div>
<div class="table-wrap"><table class="tbl"><thead><tr><th>No.</th><th>Guest</th><th>Table</th><th></th></tr></thead>
<tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.guest }}</td><td>{{ r.table }}</td><td>{{ r.get_status_display }}</td></tr>{% empty %}<tr><td colspan="4">Quiet service.</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1>{% if kind == "rsv" %}<a class="btn btn-primary" href="{% url 'reservation_new' %}">New</a>{% endif %}</div>
<div class="table-wrap"><table class="tbl"><thead><tr><th>Item</th><th></th></tr></thead>
<tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td class="muted">{% if r.seats %}{{ r.seats }} seats · {{ r.zone }}{% elif r.price %}৳ {{ r.price }}{% elif r.start %}{{ r.start }}{% endif %}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ rsv.number }}", """
<div class="card"><h1>{{ rsv.number }}</h1>
<p>{{ rsv.guest }} · {{ rsv.table }} · party {{ rsv.party_size }} · {{ rsv.get_status_display }}</p>
<form method="post">{% csrf_token %}
  {% for m in menu %}<div class="cart-row"><span>{{ m.name }} ৳ {{ m.price }}</span><input name="q_{{ m.pk }}" value="0" size="3"></div>{% endfor %}
  <button class="btn btn-primary mt-2" type="submit">Fire kitchen ticket</button>
</form></div>
"""))
    w(base / "templates/app/form.html", page("{{ title }}", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Guest</label><input class="form-control" name="name" required></div>
  <div class="form-group"><label class="form-label">Phone</label><input class="form-control" name="phone"></div>
  <div class="form-group"><label class="form-label">Table</label>
    <select name="table" class="form-control">{% for t in tables %}<option value="{{ t.pk }}">{{ t }}</option>{% endfor %}</select></div>
  <div class="form-group"><label class="form-label">Party</label><input class="form-control" name="party" value="2"></div>
  <div class="form-group"><label class="form-label">Start</label><input class="form-control" type="datetime-local" name="start"></div>
  <button class="btn btn-primary" type="submit">Book</button>
</form></div>
"""))
    w(base / "templates/app/kitchen.html", page("Kitchen", """
<div class="page-head"><h1>The pass</h1></div>
{% for t in tickets %}<div class="card"><strong>{{ t.reservation.number }}</strong> · {{ t.reservation.table }}
  <ul>{% for l in t.lines.all %}<li>{{ l.qty }} × {{ l.item }}</li>{% endfor %}</ul></div>{% empty %}
<p class="muted">No tickets.</p>{% endfor %}
"""))
    w(base / "templates/account/profile.html", PROFILE_TMPL)
    w(base / "static/css/style.css", css("  --bg:#140a08; --bg-2:#1c100e; --surface:#1c100e; --surface-2:#2a1612; --ink:#f8efe6; --muted:#c4a990; --line:rgba(255,180,80,.12); --brand:#ff7a45; --brand-2:#ffb020; --amber:#ffd56a; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#ffb020; --radius:16px; --shadow:0 18px 50px rgba(0,0,0,.35); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;"))
    w(base / "README.md", readme("TideTable", "Restaurant operating system — floor, reservations, kitchen",
        "- A table never takes a party larger than its seats.\n- Two covers cannot share a 90-minute window on the same table.\n- Kitchen tickets refuse empty or cancelled reservations."))
    print("  TideTable")


def run_all(builders):
    mapping = {
        "tidetable": "20-tidetable",
        "parcelio": "21-parcelio",
        "aurorarealty": "22-aurorarealty",
        "salonova": "23-salonova",
        "vaultsign": "24-vaultsign",
        "civicpulse": "25-civicpulse",
        "fleetnova": "26-fleetnova",
        "orbitpay": "27-orbitpay",
        "pulsegrid": "28-pulsegrid",
        "lexora": "29-lexora",
    }
    for fn in builders:
        slug = fn.__name__.replace("build_", "")
        directory = mapping[slug]
        base = ROOT / "projects" / directory
        (base / "core/management/commands").mkdir(parents=True, exist_ok=True)
        (base / "core/management/__init__.py").write_text("", encoding="utf-8")
        (base / "core/management/commands/__init__.py").write_text("", encoding="utf-8")
        fn(base)
    print("wave 4 written")


def main():
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import wave4_rest
    import wave4_more
    import wave4_last
    run_all([build_tidetable] + wave4_rest.BUILDERS + wave4_more.BUILDERS + wave4_last.BUILDERS)


if __name__ == "__main__":
    main()
