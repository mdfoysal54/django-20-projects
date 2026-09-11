"""Wave-4 builders 23–29."""
from __future__ import annotations

from wave4_build import page, profile_view, seed_users, urls, w
from wave4_rest import _shell


def build_salonova(base):
    w(base / "core/models.py", '''
"""Salonova — appointments, stylists, chairs."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Stylist(models.Model):
    name = models.CharField(max_length=80)
    specialty = models.CharField(max_length=40, default="cut")
    def __str__(self):
        return self.name

class Service(models.Model):
    name = models.CharField(max_length=80)
    minutes = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=24, blank=True)
    def __str__(self):
        return self.name

class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOK = "book", "Booked"
        IN = "in", "In chair"
        DONE = "done", "Done"
        CX = "cx", "Cancelled"
    number = models.CharField(max_length=20, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="appointments")
    stylist = models.ForeignKey(Stylist, on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    start = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.BOOK)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%Y%m%d")
            n = Appointment.objects.filter(number__startswith=f"APT-{day}").count() + 1
            self.number = f"APT-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("appointment_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number
''')
    w(base / "core/services.py", '''
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Appointment

class DomainError(ValueError):
    pass

@transaction.atomic
def book(*, client, stylist, service, start):
    if start < timezone.now() - timedelta(minutes=5):
        raise DomainError("Cannot book in the past.")
    end = start + timedelta(minutes=service.minutes)
    clash = Appointment.objects.filter(stylist=stylist, status__in=("book", "in"))
    for other in clash:
        o_end = other.start + timedelta(minutes=other.service.minutes)
        if start < o_end and end > other.start:
            raise DomainError(f"{stylist} is already in chair then.")
    return Appointment.objects.create(client=client, stylist=stylist, service=service, start=start)

@transaction.atomic
def complete(appt):
    if appt.status == Appointment.Status.CX:
        raise DomainError("Cancelled chairs cannot complete.")
    appt.status = Appointment.Status.DONE
    appt.save(update_fields=["status"])
    return appt
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Appointment, Client, Service, Stylist
from .services import DomainError, book, complete

NAV = [("Floor", [("dashboard", "Chairs"), ("appointment_list", "Bookings"), ("appointment_new", "Book")]),
       ("Menu", [("service_list", "Services")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    rows = Appointment.objects.select_related("client", "stylist", "service").order_by("start")[:40]
    return render(request, "app/dashboard.html", _ctx(request, rows=rows,
        n=rows.count(), live=Appointment.objects.filter(status="book").count()))

@login_required
def appointment_list(request):
    return render(request, "app/list.html", _ctx(request, title="Bookings",
        rows=Appointment.objects.select_related("client", "stylist"), kind="apt"))

@login_required
def appointment_detail(request, number):
    appt = get_object_or_404(Appointment, number=number)
    if request.method == "POST":
        try:
            complete(appt)
            messages.success(request, "Chair cleared.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(appt)
    return render(request, "app/detail.html", _ctx(request, appt=appt))

@login_required
def appointment_new(request):
    if request.method == "POST":
        try:
            client, _ = Client.objects.get_or_create(name=request.POST.get("name") or "Guest")
            stylist = get_object_or_404(Stylist, pk=request.POST.get("stylist"))
            service = get_object_or_404(Service, pk=request.POST.get("service"))
            start = parse_datetime(request.POST.get("start") or "") or timezone.now()
            if timezone.is_naive(start):
                start = timezone.make_aware(start)
            appt = book(client=client, stylist=stylist, service=service, start=start)
            return redirect(appt)
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, stylists=Stylist.objects.all(), services=Service.objects.all()))

@login_required
def service_list(request):
    return render(request, "app/list.html", _ctx(request, title="Menu", rows=Service.objects.all(), kind="svc"))
''' + profile_view())
    w(base / "core/urls.py", urls("Salonova", '''
    path("bookings/", views.appointment_list, name="appointment_list"),
    path("bookings/new/", views.appointment_new, name="appointment_new"),
    path("bookings/<str:number>/", views.appointment_detail, name="appointment_detail"),
    path("services/", views.service_list, name="service_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Stylist, models.Service, models.Client, models.Appointment):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Client, Service, Stylist
from .services import DomainError, book

class SalonTests(TestCase):
    def setUp(self):
        self.s = Stylist.objects.create(name="Lina")
        self.svc = Service.objects.create(name="Cut", minutes=45, price=1200)
        self.c = Client.objects.create(name="Nadia")
        self.t = timezone.now() + timedelta(hours=2)
    def test_overlap(self):
        book(client=self.c, stylist=self.s, service=self.svc, start=self.t)
        with self.assertRaises(DomainError):
            book(client=Client.objects.create(name="Rafi"), stylist=self.s, service=self.svc,
                 start=self.t + timedelta(minutes=10))
    def test_past(self):
        with self.assertRaises(DomainError):
            book(client=self.c, stylist=self.s, service=self.svc, start=timezone.now() - timedelta(hours=2))
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
''')
    w(base / "core/management/commands/seed_demo.py", f'''
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Appointment, Client, Service, Stylist
from core.services import book

class Command(BaseCommand):
    help = "Seed Salonova."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        s, _ = Stylist.objects.get_or_create(name="Lina Noor")
        Stylist.objects.get_or_create(name="Rafi Cut")
        svc, _ = Service.objects.get_or_create(name="Signature cut", defaults={{"minutes": 45, "price": 1400}})
        Service.objects.get_or_create(name="Colour gloss", defaults={{"minutes": 90, "price": 3200}})
        c, _ = Client.objects.get_or_create(name="Nadia Karim")
        if not Appointment.objects.exists():
            book(client=c, stylist=s, service=svc, start=timezone.now() + timedelta(hours=4))
        self.stdout.write(self.style.SUCCESS("Salonova seeded."))
''')
    _shell(base, "Salonova", "S", "appointment_new", "Book", "chairs that never double-book.",
           "ember", "  --bg:#1a1014; --bg-2:#24181c; --surface:#24181c; --surface-2:#322028; --ink:#fde8f0; --muted:#c9a0b0; --line:rgba(255,140,180,.14); --brand:#ff7aa2; --brand-2:#ffc2d4; --amber:#ffd0a0; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#ff7aa2; --radius:18px; --shadow:0 18px 50px rgba(0,0,0,.35); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Salon OS", "A chair is a calendar — never two clients in one <em>block</em>.",
           "Overlapping services on the same stylist are refused. Completing a cancelled chair is refused.",
           [("Chair", "Stylist calendars."), ("Menu", "Minutes + price."), ("Clash", "No overlapping blocks."), ("Done", "Status you can trust.")],
           "- Stylist calendars cannot overlap.\n- No bookings in the past.\n- Cancelled appointments cannot complete.")
    w(base / "templates/app/dashboard.html", page("Chairs", """
<div class="page-head"><h1>The floor</h1><a class="btn btn-primary" href="{% url 'appointment_new' %}">Book</a></div>
<div class="grid grid-2"><div class="card stat"><div class="stat-label">On the book</div><div class="stat-value">{{ live }}</div></div>
<div class="card stat"><div class="stat-label">Today</div><div class="stat-value">{{ n }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.client }} · {{ r.stylist }}</td><td>{{ r.service }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td class="muted">{% if r.price %}৳ {{ r.price }} · {{ r.minutes }}m{% endif %}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ appt.number }}", """
<div class="card"><h1>{{ appt.number }}</h1>
<p>{{ appt.client }} with {{ appt.stylist }} · {{ appt.service }} · {{ appt.get_status_display }}</p>
<form method="post">{% csrf_token %}<button class="btn btn-primary">Mark done</button></form></div>
"""))
    w(base / "templates/app/form.html", page("Book", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Client</label><input class="form-control" name="name" required></div>
  <select name="stylist" class="form-control">{% for s in stylists %}<option value="{{ s.pk }}">{{ s }}</option>{% endfor %}</select>
  <select name="service" class="form-control mt-1">{% for s in services %}<option value="{{ s.pk }}">{{ s }} ({{ s.minutes }}m)</option>{% endfor %}</select>
  <input type="datetime-local" name="start" class="form-control mt-1">
  <button class="btn btn-primary mt-2" type="submit">Hold the chair</button>
</form></div>
"""))


def build_vaultsign(base):
    w(base / "core/models.py", '''
"""VaultSign — document rooms, envelopes, signatures."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Room(models.Model):
    name = models.CharField(max_length=80, unique=True)
    def __str__(self):
        return self.name

class Envelope(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        SIGNED = "signed", "Signed"
        VOID = "void", "Void"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="envelopes")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    def save(self, *a, **k):
        if not self.number:
            n = Envelope.objects.count() + 1
            self.number = f"ENV-{n:05d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("envelope_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Signer(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name="signers")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    signed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = ("envelope", "email")

class Event(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=24)
    note = models.CharField(max_length=160, blank=True)
''')
    w(base / "core/services.py", '''
from django.db import transaction
from django.utils import timezone
from .models import Envelope, Event, Signer

class DomainError(ValueError):
    pass

@transaction.atomic
def send(envelope):
    if envelope.status != Envelope.Status.DRAFT:
        raise DomainError("Only drafts can be sent.")
    if envelope.signers.count() < 1:
        raise DomainError("Add at least one signer.")
    envelope.status = Envelope.Status.SENT
    envelope.save()
    Event.objects.create(envelope=envelope, kind="sent")
    return envelope

@transaction.atomic
def sign(envelope, email):
    if envelope.status == Envelope.Status.VOID:
        raise DomainError("Void envelopes cannot be signed.")
    if envelope.status != Envelope.Status.SENT:
        raise DomainError("Send the envelope first.")
    signer = envelope.signers.filter(email__iexact=email).first()
    if not signer:
        raise DomainError("That email is not on this envelope.")
    if signer.signed_at:
        raise DomainError("Already signed.")
    signer.signed_at = timezone.now()
    signer.save()
    Event.objects.create(envelope=envelope, kind="signed", note=email)
    if envelope.signers.filter(signed_at__isnull=True).count() == 0:
        envelope.status = Envelope.Status.SIGNED
        envelope.save()
        Event.objects.create(envelope=envelope, kind="complete")
    return envelope

@transaction.atomic
def void(envelope):
    if envelope.status == Envelope.Status.SIGNED:
        raise DomainError("Completed envelopes are immutable.")
    envelope.status = Envelope.Status.VOID
    envelope.save()
    Event.objects.create(envelope=envelope, kind="void")
    return envelope
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Envelope, Room, Signer
from .services import DomainError, send, sign, void

NAV = [("Vault", [("dashboard", "Rooms"), ("envelope_list", "Envelopes"), ("envelope_new", "New")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Envelope.objects.all()
    return render(request, "app/dashboard.html", _ctx(request, rows=qs.order_by("-id")[:30],
        sent=qs.filter(status="sent").count(), signed=qs.filter(status="signed").count()))

@login_required
def envelope_list(request):
    return render(request, "app/list.html", _ctx(request, title="Envelopes", rows=Envelope.objects.all(), kind="env"))

@login_required
def envelope_detail(request, number):
    env = get_object_or_404(Envelope, number=number)
    if request.method == "POST":
        act = request.POST.get("act")
        try:
            if act == "add":
                Signer.objects.create(envelope=env, name=request.POST.get("name") or "Signer",
                                      email=request.POST.get("email") or "s@demo.dev")
            elif act == "send":
                send(env)
            elif act == "sign":
                sign(env, request.POST.get("email") or request.user.email)
            elif act == "void":
                void(env)
            messages.success(request, "Updated.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(env)
    return render(request, "app/detail.html", _ctx(request, env=env))

@login_required
def envelope_new(request):
    if request.method == "POST":
        room, _ = Room.objects.get_or_create(name=request.POST.get("room") or "General")
        env = Envelope.objects.create(title=request.POST.get("title") or "Agreement", room=room, owner=request.user)
        return redirect(env)
    return render(request, "app/form.html", _ctx(request, rooms=Room.objects.all()))
''' + profile_view())
    w(base / "core/urls.py", urls("VaultSign", '''
    path("envelopes/", views.envelope_list, name="envelope_list"),
    path("envelopes/new/", views.envelope_new, name="envelope_new"),
    path("envelopes/<str:number>/", views.envelope_detail, name="envelope_detail"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Room, models.Envelope, models.Signer, models.Event):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Envelope, Room, Signer
from .services import DomainError, send, sign, void

class SignTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("maya", password="x")
        self.room = Room.objects.create(name="Legal")
        self.env = Envelope.objects.create(title="NDA", room=self.room, owner=self.u)
        Signer.objects.create(envelope=self.env, name="Alice", email="alice@demo.dev")
    def test_send_needs_signer(self):
        empty = Envelope.objects.create(title="Empty", room=self.room, owner=self.u)
        with self.assertRaises(DomainError):
            send(empty)
        send(self.env)
        sign(self.env, "alice@demo.dev")
        self.env.refresh_from_db()
        self.assertEqual(self.env.status, Envelope.Status.SIGNED)
        with self.assertRaises(DomainError):
            void(self.env)
    def test_unknown_email(self):
        send(self.env)
        with self.assertRaises(DomainError):
            sign(self.env, "nobody@x.dev")
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
''')
    w(base / "core/management/commands/seed_demo.py", f'''
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Envelope, Room, Signer
from core.services import send, sign

class Command(BaseCommand):
    help = "Seed VaultSign."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        alice = User.objects.get(username="alice")
        room, _ = Room.objects.get_or_create(name="Board")
        if not Envelope.objects.exists():
            env = Envelope.objects.create(title="Series seed NDA", room=room, owner=alice)
            Signer.objects.create(envelope=env, name="Alice Rahman", email="alice@demo.dev")
            Signer.objects.create(envelope=env, name="Counsel", email="legal@demo.dev")
            send(env)
            sign(env, "alice@demo.dev")
        self.stdout.write(self.style.SUCCESS("VaultSign seeded."))
''')
    _shell(base, "VaultSign", "V", "envelope_new", "New envelope", "signatures that stick.",
           "void", "  --bg:#0a0a0c; --bg-2:#141416; --surface:#141416; --surface-2:#1c1c22; --ink:#f4ecd4; --muted:#b8a878; --line:rgba(212,175,55,.16); --brand:#d4af37; --brand-2:#f0e0a0; --amber:#d4af37; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#d4af37; --radius:14px; --shadow:0 18px 50px rgba(0,0,0,.45); --font:ui-serif,Georgia,serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Signature OS", "Envelopes that cannot be <em>rewritten</em> once complete.",
           "Drafts need a signer before send. Completed envelopes cannot be voided.",
           [("Rooms", "Vaults per team."), ("Signers", "Named, unique emails."), ("Seal", "All must sign."), ("Void", "Never after complete.")],
           "- Send requires ≥1 signer.\n- Only listed emails can sign.\n- Completed envelopes cannot be voided.")
    w(base / "templates/app/dashboard.html", page("Rooms", """
<div class="page-head"><h1>The vault</h1><a class="btn btn-primary" href="{% url 'envelope_new' %}">New envelope</a></div>
<div class="grid grid-2"><div class="card stat"><div class="stat-label">Sent</div><div class="stat-value">{{ sent }}</div></div>
<div class="card stat"><div class="stat-label">Sealed</div><div class="stat-value">{{ signed }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.title }}</td><td>{{ r.get_status_display }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r }}</a></td><td>{{ r.title }} · {{ r.get_status_display }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ env.number }}", """
<div class="card"><h1>{{ env.title }}</h1><p>{{ env.number }} · {{ env.get_status_display }}</p>
<ul>{% for s in env.signers.all %}<li>{{ s.name }} {{ s.email }} {% if s.signed_at %}✓{% endif %}</li>{% endfor %}</ul>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="add">
  <input name="name" placeholder="Name" class="form-control"><input name="email" placeholder="email" class="form-control mt-1">
  <button class="btn btn-secondary mt-2">Add signer</button></form>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="send"><button class="btn btn-primary">Send</button></form>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="sign"><input name="email" value="{{ user.email }}" class="form-control"><button class="btn btn-primary mt-1">Sign</button></form>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="void"><button class="btn btn-danger">Void</button></form>
</div>
"""))
    w(base / "templates/app/form.html", page("New envelope", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Title</label><input class="form-control" name="title" required></div>
  <div class="form-group"><label class="form-label">Room</label><input class="form-control" name="room" value="Board"></div>
  <button class="btn btn-primary">Create</button>
</form></div>
"""))


def build_civicpulse(base):
    w(base / "core/models.py", '''
"""CivicPulse — citizen issues, wards, work orders."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Ward(models.Model):
    name = models.CharField(max_length=80, unique=True)
    def __str__(self):
        return self.name

class Issue(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WORK = "work", "In works"
        DONE = "done", "Resolved"
        DUP = "dup", "Duplicate"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="issues")
    category = models.CharField(max_length=40, default="roads")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    reporter = models.CharField(max_length=80)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Issue.objects.filter(number__startswith=f"CV-{day}").count() + 1
            self.number = f"CV-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("issue_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class WorkOrder(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="orders")
    crew = models.CharField(max_length=80)
    note = models.CharField(max_length=200, blank=True)
    closed = models.BooleanField(default=False)
    opened_at = models.DateTimeField(auto_now_add=True)
''')
    w(base / "core/services.py", '''
from django.db import transaction
from .models import Issue, WorkOrder

class DomainError(ValueError):
    pass

@transaction.atomic
def dispatch(issue, crew, note=""):
    if issue.status in (Issue.Status.DONE, Issue.Status.DUP):
        raise DomainError("Closed issues cannot take new crews.")
    if not crew.strip():
        raise DomainError("Name a crew.")
    if WorkOrder.objects.filter(issue=issue, closed=False).exists():
        raise DomainError("An open work order already exists.")
    wo = WorkOrder.objects.create(issue=issue, crew=crew, note=note)
    issue.status = Issue.Status.WORK
    issue.save(update_fields=["status"])
    return wo

@transaction.atomic
def resolve(issue):
    open_wo = issue.orders.filter(closed=False)
    if not open_wo.exists():
        raise DomainError("Dispatch a crew before resolving.")
    open_wo.update(closed=True)
    issue.status = Issue.Status.DONE
    issue.save(update_fields=["status"])
    return issue
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Issue, Ward
from .services import DomainError, dispatch, resolve

NAV = [("City", [("dashboard", "Pulse"), ("issue_list", "Issues"), ("issue_new", "File")]),
       ("Map", [("ward_list", "Wards")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Issue.objects.select_related("ward")
    return render(request, "app/dashboard.html", _ctx(request, rows=qs.order_by("-id")[:30],
        open=qs.filter(status="open").count(), work=qs.filter(status="work").count(),
        done=qs.filter(status="done").count()))

@login_required
def issue_list(request):
    return render(request, "app/list.html", _ctx(request, title="Issues", rows=Issue.objects.select_related("ward"), kind="iss"))

@login_required
def issue_detail(request, number):
    issue = get_object_or_404(Issue, number=number)
    if request.method == "POST":
        try:
            if request.POST.get("act") == "dispatch":
                dispatch(issue, request.POST.get("crew") or "", request.POST.get("note") or "")
            else:
                resolve(issue)
            messages.success(request, "Updated.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(issue)
    return render(request, "app/detail.html", _ctx(request, issue=issue))

@login_required
def issue_new(request):
    if request.method == "POST":
        ward = get_object_or_404(Ward, pk=request.POST.get("ward"))
        issue = Issue.objects.create(title=request.POST.get("title") or "Issue", ward=ward,
            category=request.POST.get("cat") or "roads", reporter=request.POST.get("reporter") or request.user.username)
        return redirect(issue)
    return render(request, "app/form.html", _ctx(request, wards=Ward.objects.all()))

@login_required
def ward_list(request):
    return render(request, "app/list.html", _ctx(request, title="Wards", rows=Ward.objects.all(), kind="wrd"))
''' + profile_view())
    w(base / "core/urls.py", urls("CivicPulse", '''
    path("issues/", views.issue_list, name="issue_list"),
    path("issues/new/", views.issue_new, name="issue_new"),
    path("issues/<str:number>/", views.issue_detail, name="issue_detail"),
    path("wards/", views.ward_list, name="ward_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Ward, models.Issue, models.WorkOrder):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Issue, Ward
from .services import DomainError, dispatch, resolve

class CivicTests(TestCase):
    def setUp(self):
        self.w = Ward.objects.create(name="Ward 19")
        self.i = Issue.objects.create(title="Pothole", ward=self.w, reporter="Nadia")
    def test_resolve_needs_crew(self):
        with self.assertRaises(DomainError):
            resolve(self.i)
        dispatch(self.i, "Roads A")
        with self.assertRaises(DomainError):
            dispatch(self.i, "Roads B")
        resolve(self.i)
        self.i.refresh_from_db()
        self.assertEqual(self.i.status, Issue.Status.DONE)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
''')
    w(base / "core/management/commands/seed_demo.py", f'''
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Issue, Ward
from core.services import dispatch

class Command(BaseCommand):
    help = "Seed CivicPulse."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        w, _ = Ward.objects.get_or_create(name="Ward 19")
        Ward.objects.get_or_create(name="Ward 27")
        if not Issue.objects.exists():
            i = Issue.objects.create(title="Open manhole, Road 11", ward=w, category="safety", reporter="Nadia Karim")
            dispatch(i, "Public Works North", "Barricade tonight")
        self.stdout.write(self.style.SUCCESS("CivicPulse seeded."))
''')
    _shell(base, "CivicPulse", "C", "issue_new", "File issue", "the city, in tickets.",
           "light", "  --bg:#f3f5fb; --bg-2:#fff; --surface:#fff; --surface-2:#e8eef8; --ink:#10203a; --muted:#4a5a78; --line:#d5deee; --brand:#1d4ed8; --brand-2:#0ea5e9; --amber:#f59e0b; --ok:#059669; --warn:#d97706; --bad:#dc2626; --info:#1d4ed8; --radius:16px; --shadow:0 16px 40px rgba(20,40,80,.08); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Civic OS", "Wards, issues and crews — a city that <em>closes</em> its loops.",
           "No resolve without a crew. One open work order at a time.",
           [("Wards", "Geography first."), ("Issues", "Numbered tickets."), ("Crews", "One open order."), ("Close", "Resolve only after dispatch.")],
           "- Resolve requires an open work order.\n- One open work order per issue.\n- Closed / duplicate issues cannot dispatch.")
    w(base / "templates/app/dashboard.html", page("Pulse", """
<div class="page-head"><h1>The city tonight</h1><a class="btn btn-primary" href="{% url 'issue_new' %}">File</a></div>
<div class="grid grid-3"><div class="card stat"><div class="stat-label">Open</div><div class="stat-value">{{ open }}</div></div>
<div class="card stat"><div class="stat-label">Works</div><div class="stat-value">{{ work }}</div></div>
<div class="card stat"><div class="stat-label">Resolved</div><div class="stat-value">{{ done }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.title }}</td><td>{{ r.ward }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td>{{ r.title|default:"" }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ issue.number }}", """
<div class="card"><h1>{{ issue.title }}</h1>
<p>{{ issue.number }} · {{ issue.ward }} · {{ issue.get_status_display }}</p>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="dispatch">
  <input name="crew" placeholder="Crew" class="form-control">
  <input name="note" placeholder="Note" class="form-control mt-1">
  <button class="btn btn-primary mt-2">Dispatch</button></form>
<form method="post">{% csrf_token %}<button class="btn btn-secondary">Resolve</button></form>
</div>
"""))
    w(base / "templates/app/form.html", page("File", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Title</label><input class="form-control" name="title" required></div>
  <select name="ward" class="form-control">{% for w in wards %}<option value="{{ w.pk }}">{{ w }}</option>{% endfor %}</select>
  <input name="cat" class="form-control mt-1" value="roads">
  <input name="reporter" class="form-control mt-1" placeholder="Reporter">
  <button class="btn btn-primary mt-2">File</button>
</form></div>
"""))


def build_fleetnova(base):
    w(base / "core/models.py", '''
"""FleetNova — vehicles, trips, fuel."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Vehicle(models.Model):
    plate = models.CharField(max_length=16, unique=True)
    kind = models.CharField(max_length=24, default="van")
    odometer = models.PositiveIntegerField(default=0)
    def __str__(self):
        return self.plate

class Driver(models.Model):
    name = models.CharField(max_length=80)
    licence = models.CharField(max_length=24, unique=True)
    def __str__(self):
        return self.name

class Trip(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSE = "close", "Closed"
    number = models.CharField(max_length=20, unique=True, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="trips")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="trips")
    origin = models.CharField(max_length=80)
    dest = models.CharField(max_length=80)
    start_km = models.PositiveIntegerField()
    end_km = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Trip.objects.filter(number__startswith=f"TR-{day}").count() + 1
            self.number = f"TR-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("trip_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class FuelLog(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="fuel")
    litres = models.DecimalField(max_digits=8, decimal_places=2)
    km = models.PositiveIntegerField()
    at = models.DateTimeField(auto_now_add=True)
''')
    w(base / "core/services.py", '''
from django.db import transaction
from .models import FuelLog, Trip

class DomainError(ValueError):
    pass

@transaction.atomic
def open_trip(*, vehicle, driver, origin, dest, start_km):
    if start_km < vehicle.odometer:
        raise DomainError("Start km cannot rewind the odometer.")
    if Trip.objects.filter(vehicle=vehicle, status=Trip.Status.OPEN).exists():
        raise DomainError("This vehicle is already on a trip.")
    if Trip.objects.filter(driver=driver, status=Trip.Status.OPEN).exists():
        raise DomainError("This driver is already on a trip.")
    return Trip.objects.create(vehicle=vehicle, driver=driver, origin=origin, dest=dest, start_km=start_km)

@transaction.atomic
def close_trip(trip, end_km):
    if trip.status != Trip.Status.OPEN:
        raise DomainError("Trip already closed.")
    if end_km < trip.start_km:
        raise DomainError("End km cannot be below start km.")
    trip.end_km = end_km
    trip.status = Trip.Status.CLOSE
    trip.save()
    v = trip.vehicle
    v.odometer = end_km
    v.save(update_fields=["odometer"])
    return trip

@transaction.atomic
def fuel(vehicle, litres, km):
    if litres <= 0:
        raise DomainError("Litres must be positive.")
    if km < vehicle.odometer:
        raise DomainError("Fuel km cannot rewind the odometer.")
    return FuelLog.objects.create(vehicle=vehicle, litres=litres, km=km)
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Driver, Trip, Vehicle
from .services import DomainError, close_trip, fuel, open_trip

NAV = [("Fleet", [("dashboard", "Yard"), ("trip_list", "Trips"), ("trip_new", "Dispatch")]),
       ("Assets", [("vehicle_list", "Vehicles")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    return render(request, "app/dashboard.html", _ctx(request,
        n_v=Vehicle.objects.count(), open=Trip.objects.filter(status="open").count(),
        rows=Trip.objects.select_related("vehicle", "driver").order_by("-id")[:25]))

@login_required
def trip_list(request):
    return render(request, "app/list.html", _ctx(request, title="Trips",
        rows=Trip.objects.select_related("vehicle", "driver"), kind="trp"))

@login_required
def trip_detail(request, number):
    trip = get_object_or_404(Trip, number=number)
    if request.method == "POST":
        try:
            close_trip(trip, int(request.POST.get("end_km") or 0))
            messages.success(request, "Trip closed.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(trip)
    return render(request, "app/detail.html", _ctx(request, trip=trip))

@login_required
def trip_new(request):
    if request.method == "POST":
        try:
            trip = open_trip(vehicle=get_object_or_404(Vehicle, pk=request.POST.get("vehicle")),
                             driver=get_object_or_404(Driver, pk=request.POST.get("driver")),
                             origin=request.POST.get("origin") or "Yard",
                             dest=request.POST.get("dest") or "Site",
                             start_km=int(request.POST.get("start_km") or 0))
            return redirect(trip)
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, vehicles=Vehicle.objects.all(), drivers=Driver.objects.all()))

@login_required
def vehicle_list(request):
    if request.method == "POST":
        try:
            v = get_object_or_404(Vehicle, pk=request.POST.get("vehicle"))
            fuel(v, float(request.POST.get("litres") or 0), int(request.POST.get("km") or v.odometer))
            messages.success(request, "Fuel logged.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect("vehicle_list")
    return render(request, "app/list.html", _ctx(request, title="Vehicles", rows=Vehicle.objects.all(), kind="veh"))
''' + profile_view())
    w(base / "core/urls.py", urls("FleetNova", '''
    path("trips/", views.trip_list, name="trip_list"),
    path("trips/new/", views.trip_new, name="trip_new"),
    path("trips/<str:number>/", views.trip_detail, name="trip_detail"),
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Vehicle, models.Driver, models.Trip, models.FuelLog):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Driver, Vehicle
from .services import DomainError, close_trip, open_trip

class FleetTests(TestCase):
    def setUp(self):
        self.v = Vehicle.objects.create(plate="DHK-101", odometer=1000)
        self.d = Driver.objects.create(name="Karim", licence="DL-1")
    def test_double_dispatch(self):
        open_trip(vehicle=self.v, driver=self.d, origin="A", dest="B", start_km=1000)
        with self.assertRaises(DomainError):
            open_trip(vehicle=self.v, driver=Driver.objects.create(name="B", licence="DL-2"),
                      origin="A", dest="C", start_km=1000)
    def test_rewind(self):
        t = open_trip(vehicle=self.v, driver=self.d, origin="A", dest="B", start_km=1000)
        with self.assertRaises(DomainError):
            close_trip(t, 800)
class Pages(TestCase):
    def test_home(self):
        self.assertEqual(self.client.get("/").status_code, 200)
    def test_login(self):
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)
    def test_seed(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
''')
    w(base / "core/management/commands/seed_demo.py", f'''
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from core.models import Driver, Trip, Vehicle
from core.services import open_trip

class Command(BaseCommand):
    help = "Seed FleetNova."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        v, _ = Vehicle.objects.get_or_create(plate="DHK-METRO-09", defaults={{"kind": "truck", "odometer": 48200}})
        d, _ = Driver.objects.get_or_create(licence="DL-DHK-77", defaults={{"name": "Karim Uddin"}})
        if not Trip.objects.exists():
            open_trip(vehicle=v, driver=d, origin="Tejgaon yard", dest="Chittagong port", start_km=48200)
        self.stdout.write(self.style.SUCCESS("FleetNova seeded."))
''')
    _shell(base, "FleetNova", "F", "trip_new", "Dispatch", "odometers that only go forward.",
           "ember", "  --bg:#0c0c10; --bg-2:#16161c; --surface:#16161c; --surface-2:#22222c; --ink:#f4f0e6; --muted:#a8a090; --line:rgba(255,176,32,.14); --brand:#ffb020; --brand-2:#ff7a45; --amber:#ffb020; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#ffb020; --radius:14px; --shadow:0 18px 50px rgba(0,0,0,.4); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Fleet OS", "One vehicle, one driver, one <em>open</em> trip.",
           "Odometers never rewind. Vehicles and drivers cannot double-dispatch.",
           [("Yard", "Plates and km."), ("Trip", "One open run."), ("Fuel", "Litres vs km."), ("Close", "End km ≥ start.")],
           "- One open trip per vehicle and per driver.\n- Start km ≥ odometer.\n- End km ≥ start km.")
    w(base / "templates/app/dashboard.html", page("Yard", """
<div class="page-head"><h1>The yard</h1><a class="btn btn-primary" href="{% url 'trip_new' %}">Dispatch</a></div>
<div class="grid grid-2"><div class="card stat"><div class="stat-label">Vehicles</div><div class="stat-value">{{ n_v }}</div></div>
<div class="card stat"><div class="stat-label">Open trips</div><div class="stat-value">{{ open }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.vehicle }} · {{ r.driver }}</td><td>{{ r.origin }} → {{ r.dest }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
{% if kind == "veh" %}<form method="post" class="card">{% csrf_token %}
  <select name="vehicle">{% for r in rows %}<option value="{{ r.pk }}">{{ r.plate }} ({{ r.odometer }} km)</option>{% endfor %}</select>
  <input name="litres" placeholder="L" size="4"> <input name="km" placeholder="km" size="6">
  <button class="btn btn-primary">Log fuel</button></form>{% endif %}
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td class="muted">{% if r.odometer %}{{ r.odometer }} km{% endif %}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ trip.number }}", """
<div class="card"><h1>{{ trip.number }}</h1>
<p>{{ trip.vehicle }} · {{ trip.driver }} · {{ trip.origin }} → {{ trip.dest }} · {{ trip.start_km }} km</p>
<form method="post">{% csrf_token %}<input name="end_km" placeholder="End km" class="form-control">
  <button class="btn btn-primary mt-2">Close trip</button></form></div>
"""))
    w(base / "templates/app/form.html", page("Dispatch", """
<div class="card"><form method="post">{% csrf_token %}
  <select name="vehicle" class="form-control">{% for v in vehicles %}<option value="{{ v.pk }}">{{ v }}</option>{% endfor %}</select>
  <select name="driver" class="form-control mt-1">{% for d in drivers %}<option value="{{ d.pk }}">{{ d }}</option>{% endfor %}</select>
  <input name="origin" class="form-control mt-1" placeholder="Origin">
  <input name="dest" class="form-control mt-1" placeholder="Dest">
  <input name="start_km" class="form-control mt-1" placeholder="Start km">
  <button class="btn btn-primary mt-2">Open trip</button>
</form></div>
"""))


BUILDERS = [build_salonova, build_vaultsign, build_civicpulse, build_fleetnova]
