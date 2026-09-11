"""Wave-4 builders 21–22 (Parcelio, AuroraRealty)."""
from __future__ import annotations

from wave4_build import (
    PROFILE_TMPL,
    base_html,
    css,
    landing,
    page,
    profile_view,
    readme,
    seed_users,
    urls,
    w,
)


def build_parcelio(base):
    w(base / "core/models.py", '''
"""Parcelio — last-mile courier OS."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Station(models.Model):
    name = models.CharField(max_length=80, unique=True)
    city = models.CharField(max_length=60)
    def __str__(self):
        return self.name

class Courier(models.Model):
    name = models.CharField(max_length=80)
    station = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="couriers")
    active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class Parcel(models.Model):
    class Status(models.TextChoices):
        CREATED = "new", "Created"
        HUB = "hub", "At hub"
        OUT = "out", "Out for delivery"
        DONE = "done", "Delivered"
        RET = "ret", "Returned"
    number = models.CharField(max_length=22, unique=True, editable=False)
    sender = models.CharField(max_length=80)
    recipient = models.CharField(max_length=80)
    dest_city = models.CharField(max_length=60)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    origin = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="outbound")
    courier = models.ForeignKey(Courier, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.CREATED)
    cod = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Parcel.objects.filter(number__startswith=f"PCL-{day}").count() + 1
            self.number = f"PCL-{day}-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("parcel_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Scan(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="scans")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=16)
    note = models.CharField(max_length=120, blank=True)
''')
    w(base / "core/services.py", '''
from django.db import transaction
from .models import Parcel, Scan

class DomainError(ValueError):
    pass

MAX_KG = 30

@transaction.atomic
def intake(*, sender, recipient, dest_city, weight_kg, origin, cod=0):
    if float(weight_kg) <= 0:
        raise DomainError("Weight must be positive.")
    if float(weight_kg) > MAX_KG:
        raise DomainError("Parcels over 30 kg need freight, not last-mile.")
    p = Parcel.objects.create(sender=sender, recipient=recipient, dest_city=dest_city,
                              weight_kg=weight_kg, origin=origin, cod=cod)
    Scan.objects.create(parcel=p, kind="created", note=origin.name)
    return p

@transaction.atomic
def advance(parcel, courier=None):
    order = [Parcel.Status.CREATED, Parcel.Status.HUB, Parcel.Status.OUT, Parcel.Status.DONE]
    if parcel.status == Parcel.Status.RET:
        raise DomainError("Returned parcels stay returned.")
    if parcel.status == Parcel.Status.DONE:
        raise DomainError("Already delivered.")
    nxt = order[order.index(parcel.status) + 1]
    if nxt == Parcel.Status.OUT and courier is None and parcel.courier is None:
        raise DomainError("Assign a courier before last-mile.")
    if courier:
        if courier.station_id != parcel.origin_id and nxt == Parcel.Status.HUB:
            pass
        parcel.courier = courier
    parcel.status = nxt
    parcel.save()
    Scan.objects.create(parcel=parcel, kind=nxt, note=str(parcel.courier or ""))
    return parcel
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Courier, Parcel, Station
from .services import DomainError, advance, intake

NAV = [("Ops", [("dashboard", "Hub"), ("parcel_list", "Parcels"), ("parcel_new", "Intake")]),
       ("People", [("courier_list", "Couriers")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Parcel.objects.all()
    return render(request, "app/dashboard.html", _ctx(request, n=qs.count(),
        out=qs.filter(status="out").count(), done=qs.filter(status="done").count(),
        rows=qs.order_by("-id")[:20]))

@login_required
def parcel_list(request):
    return render(request, "app/list.html", _ctx(request, title="Parcels",
        rows=Parcel.objects.select_related("origin", "courier").order_by("-id")[:100], kind="pcl"))

@login_required
def parcel_detail(request, number):
    p = get_object_or_404(Parcel, number=number)
    if request.method == "POST":
        cid = request.POST.get("courier")
        courier = Courier.objects.filter(pk=cid).first() if cid else p.courier
        try:
            advance(p, courier=courier)
            messages.success(request, f"Now {p.get_status_display()}.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(p)
    return render(request, "app/detail.html", _ctx(request, p=p, couriers=Courier.objects.filter(active=True)))

@login_required
def parcel_new(request):
    if request.method == "POST":
        try:
            origin = get_object_or_404(Station, pk=request.POST.get("origin"))
            p = intake(sender=request.POST.get("sender") or "Sender",
                       recipient=request.POST.get("recipient") or "Recipient",
                       dest_city=request.POST.get("dest") or origin.city,
                       weight_kg=request.POST.get("kg") or 1,
                       origin=origin, cod=request.POST.get("cod") or 0)
            messages.success(request, p.number)
            return redirect(p)
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, stations=Station.objects.all()))

@login_required
def courier_list(request):
    return render(request, "app/list.html", _ctx(request, title="Couriers",
        rows=Courier.objects.select_related("station"), kind="crr"))
''' + profile_view())
    w(base / "core/urls.py", urls("Parcelio", '''
    path("parcels/", views.parcel_list, name="parcel_list"),
    path("parcels/new/", views.parcel_new, name="parcel_new"),
    path("parcels/<str:number>/", views.parcel_detail, name="parcel_detail"),
    path("couriers/", views.courier_list, name="courier_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Station, models.Courier, models.Parcel, models.Scan):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Courier, Station
from .services import DomainError, advance, intake

class ParcelTests(TestCase):
    def setUp(self):
        self.st = Station.objects.create(name="Gulshan Hub", city="Dhaka")
        self.c = Courier.objects.create(name="Rafi", station=self.st)
    def test_weight_cap(self):
        with self.assertRaises(DomainError):
            intake(sender="A", recipient="B", dest_city="Chittagong", weight_kg=40, origin=self.st)
    def test_needs_courier(self):
        p = intake(sender="A", recipient="B", dest_city="Sylhet", weight_kg=2, origin=self.st)
        p = advance(p)
        with self.assertRaises(DomainError):
            advance(p)
        advance(p, courier=self.c)
        self.assertEqual(p.status, "out")
    def test_no_reopen(self):
        p = intake(sender="A", recipient="B", dest_city="Sylhet", weight_kg=1, origin=self.st)
        p.status = "done"; p.save()
        with self.assertRaises(DomainError):
            advance(p)
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
from core.models import Courier, Parcel, Station
from core.services import advance, intake

class Command(BaseCommand):
    help = "Seed Parcelio."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        st, _ = Station.objects.get_or_create(name="Gulshan Hub", defaults={{"city": "Dhaka"}})
        Station.objects.get_or_create(name="Agrabad", defaults={{"city": "Chittagong"}})
        c, _ = Courier.objects.get_or_create(name="Rafi Hasan", defaults={{"station": st}})
        if not Parcel.objects.exists():
            p = intake(sender="Nexora Ltd", recipient="CampusOS", dest_city="Sylhet", weight_kg=2.4, origin=st, cod=450)
            advance(p); advance(p, courier=c)
        self.stdout.write(self.style.SUCCESS("Parcelio seeded."))
''')
    _shell(base, "Parcelio", "P", "parcel_new", "Intake", "last mile, first class.",
           "void", "  --bg:#070b08; --bg-2:#101610; --surface:#101610; --surface-2:#182018; --ink:#e8ffe8; --muted:#8fb89a; --line:rgba(80,255,140,.12); --brand:#7CFF6B; --brand-2:#c8ff4a; --amber:#d0ff5e; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#7CFF6B; --radius:16px; --shadow:0 18px 50px rgba(0,0,0,.4); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Courier OS", "Every parcel has a number, a hub and a <em>honest</em> last mile.",
           "Weight cap 30 kg. Courier required before out-for-delivery. Delivered stays delivered.",
           [("Scan", "Every state change is a scan."), ("Hubs", "Stations own the fleet."), ("COD", "Cash on delivery tracked."), ("Cap", "30 kg last-mile ceiling.")],
           "- Weight must be ≤ 30 kg.\n- Out-for-delivery requires a courier.\n- Delivered / returned parcels cannot advance.")
    w(base / "templates/app/dashboard.html", page("Hub", """
<div class="page-head"><h1>Tonight's bag</h1><a class="btn btn-primary" href="{% url 'parcel_new' %}">Intake</a></div>
<div class="grid grid-3"><div class="card stat"><div class="stat-label">Parcels</div><div class="stat-value">{{ n }}</div></div>
<div class="card stat"><div class="stat-label">Out</div><div class="stat-value">{{ out }}</div></div>
<div class="card stat"><div class="stat-label">Delivered</div><div class="stat-value">{{ done }}</div></div></div>
<div class="table-wrap"><table class="tbl"><thead><tr><th>No.</th><th>To</th><th></th></tr></thead>
<tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.recipient }} · {{ r.dest_city }}</td><td>{{ r.get_status_display }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td class="muted">{{ r.dest_city|default:r.station }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ p.number }}", """
<div class="card"><h1>{{ p.number }}</h1>
<p>{{ p.sender }} → {{ p.recipient }} · {{ p.weight_kg }} kg · {{ p.get_status_display }}</p>
<form method="post">{% csrf_token %}
  <select name="courier" class="form-control">{% for c in couriers %}<option value="{{ c.pk }}">{{ c }}</option>{% endfor %}</select>
  <button class="btn btn-primary mt-2" type="submit">Advance</button>
</form>
<ul>{% for s in p.scans.all %}<li>{{ s.at }} · {{ s.kind }}</li>{% endfor %}</ul></div>
"""))
    w(base / "templates/app/form.html", page("Intake", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Sender</label><input class="form-control" name="sender" required></div>
  <div class="form-group"><label class="form-label">Recipient</label><input class="form-control" name="recipient" required></div>
  <div class="form-group"><label class="form-label">City</label><input class="form-control" name="dest"></div>
  <div class="form-group"><label class="form-label">Kg</label><input class="form-control" name="kg" value="1.0"></div>
  <div class="form-group"><label class="form-label">COD</label><input class="form-control" name="cod" value="0"></div>
  <div class="form-group"><label class="form-label">Origin</label>
    <select name="origin" class="form-control">{% for s in stations %}<option value="{{ s.pk }}">{{ s }}</option>{% endfor %}</select></div>
  <button class="btn btn-primary" type="submit">Create AWB</button>
</form></div>
"""))


def build_aurorarealty(base):
    w(base / "core/models.py", '''
"""AuroraRealty — listings, viewings, offers."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Agent(models.Model):
    name = models.CharField(max_length=80)
    licence = models.CharField(max_length=24, unique=True)
    def __str__(self):
        return self.name

class Listing(models.Model):
    class Status(models.TextChoices):
        LIVE = "live", "Live"
        HOLD = "hold", "Under offer"
        SOLD = "sold", "Sold"
        OFF = "off", "Withdrawn"
    code = models.CharField(max_length=16, unique=True, editable=False)
    title = models.CharField(max_length=140)
    suburb = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    beds = models.PositiveSmallIntegerField()
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="listings")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.LIVE)
    def save(self, *a, **k):
        if not self.code:
            n = Listing.objects.count() + 1
            self.code = f"AR-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("listing_detail", kwargs={"code": self.code})
    def __str__(self):
        return self.code

class Viewing(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="viewings")
    when = models.DateTimeField()
    visitor = models.CharField(max_length=80)
    class Meta:
        unique_together = ("listing", "when", "visitor")

class Offer(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WIN = "win", "Accepted"
        LOSE = "lose", "Declined"
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="offers")
    buyer = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created = models.DateTimeField(auto_now_add=True)
''')
    w(base / "core/services.py", '''
from django.db import transaction
from django.utils import timezone
from .models import Listing, Offer, Viewing

class DomainError(ValueError):
    pass

@transaction.atomic
def book_viewing(listing, when, visitor):
    if listing.status != Listing.Status.LIVE:
        raise DomainError("Only live listings take viewings.")
    if when < timezone.now():
        raise DomainError("Viewings cannot be in the past.")
    if Viewing.objects.filter(listing=listing, when=when).exists():
        raise DomainError("That slot is already taken.")
    return Viewing.objects.create(listing=listing, when=when, visitor=visitor)

@transaction.atomic
def place_offer(listing, buyer, amount):
    if listing.status in (Listing.Status.SOLD, Listing.Status.OFF):
        raise DomainError("This listing is closed.")
    if amount <= 0:
        raise DomainError("Offer must be positive.")
    floor = listing.price * 80 / 100
    if amount < floor:
        raise DomainError("Offers below 80% of asking are rejected.")
    offer = Offer.objects.create(listing=listing, buyer=buyer, amount=amount)
    listing.status = Listing.Status.HOLD
    listing.save(update_fields=["status"])
    return offer

@transaction.atomic
def accept_offer(offer):
    if offer.status != Offer.Status.OPEN:
        raise DomainError("Offer is not open.")
    offer.status = Offer.Status.WIN
    offer.save()
    listing = offer.listing
    listing.status = Listing.Status.SOLD
    listing.save()
    Offer.objects.filter(listing=listing, status=Offer.Status.OPEN).exclude(pk=offer.pk).update(status=Offer.Status.LOSE)
    return offer
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Agent, Listing, Offer
from .services import DomainError, accept_offer, book_viewing, place_offer

NAV = [("Desk", [("dashboard", "Pipeline"), ("listing_list", "Listings"), ("listing_new", "New listing")]),
       ("Deals", [("offer_list", "Offers")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Listing.objects.select_related("agent")
    return render(request, "app/dashboard.html", _ctx(request, rows=qs,
        live=qs.filter(status="live").count(), hold=qs.filter(status="hold").count(),
        sold=qs.filter(status="sold").count()))

@login_required
def listing_list(request):
    return render(request, "app/list.html", _ctx(request, title="Listings", rows=Listing.objects.all(), kind="lst"))

@login_required
def listing_detail(request, code):
    listing = get_object_or_404(Listing, code=code)
    if request.method == "POST":
        act = request.POST.get("act")
        try:
            if act == "view":
                when = parse_datetime(request.POST.get("when") or "") or timezone.now()
                if timezone.is_naive(when):
                    when = timezone.make_aware(when)
                book_viewing(listing, when, request.POST.get("visitor") or request.user.get_full_name() or "Visitor")
                messages.success(request, "Viewing booked.")
            elif act == "offer":
                place_offer(listing, request.POST.get("buyer") or "Buyer", float(request.POST.get("amount") or 0))
                messages.success(request, "Offer lodged.")
            elif act == "accept":
                offer = get_object_or_404(Offer, pk=request.POST.get("offer"), listing=listing)
                accept_offer(offer)
                messages.success(request, "Sold.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(listing)
    return render(request, "app/detail.html", _ctx(request, listing=listing))

@login_required
def listing_new(request):
    if request.method == "POST":
        agent = get_object_or_404(Agent, pk=request.POST.get("agent"))
        listing = Listing.objects.create(title=request.POST.get("title") or "Home",
            suburb=request.POST.get("suburb") or "Gulshan",
            price=request.POST.get("price") or 10000000, beds=int(request.POST.get("beds") or 3), agent=agent)
        return redirect(listing)
    return render(request, "app/form.html", _ctx(request, agents=Agent.objects.all()))

@login_required
def offer_list(request):
    return render(request, "app/list.html", _ctx(request, title="Offers", rows=Offer.objects.select_related("listing"), kind="off"))
''' + profile_view())
    w(base / "core/urls.py", urls("AuroraRealty", '''
    path("listings/", views.listing_list, name="listing_list"),
    path("listings/new/", views.listing_new, name="listing_new"),
    path("listings/<str:code>/", views.listing_detail, name="listing_detail"),
    path("offers/", views.offer_list, name="offer_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Agent, models.Listing, models.Viewing, models.Offer):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Agent, Listing, Offer
from .services import DomainError, accept_offer, book_viewing, place_offer

class RealtyTests(TestCase):
    def setUp(self):
        self.a = Agent.objects.create(name="Maya", licence="REA-1")
        self.l = Listing.objects.create(title="Lakeview", suburb="Gulshan", price=20000000, beds=3, agent=self.a)
    def test_lowball(self):
        with self.assertRaises(DomainError):
            place_offer(self.l, "Buyer", 1000000)
    def test_accept_closes_others(self):
        o1 = place_offer(self.l, "A", 18000000)
        o2 = place_offer(self.l, "B", 19000000)
        accept_offer(o2)
        o1.refresh_from_db(); self.l.refresh_from_db()
        self.assertEqual(o1.status, Offer.Status.LOSE)
        self.assertEqual(self.l.status, Listing.Status.SOLD)
        with self.assertRaises(DomainError):
            book_viewing(self.l, timezone.now() + timedelta(days=1), "X")
    def test_past_viewing(self):
        with self.assertRaises(DomainError):
            book_viewing(self.l, timezone.now() - timedelta(days=1), "X")
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
from core.models import Agent, Listing
from core.services import book_viewing, place_offer

class Command(BaseCommand):
    help = "Seed AuroraRealty."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        ag, _ = Agent.objects.get_or_create(licence="REA-DHK-01", defaults={{"name": "Maya Rahman"}})
        if not Listing.objects.exists():
            l = Listing.objects.create(title="North Lake penthouse", suburb="Gulshan", price=42000000, beds=4, agent=ag)
            Listing.objects.create(title="River duplex", suburb="Baridhara", price=28000000, beds=3, agent=ag)
            book_viewing(l, timezone.now() + timedelta(days=2), "Nadia Karim")
            place_offer(l, "OrbitPay Ltd", 40000000)
        self.stdout.write(self.style.SUCCESS("AuroraRealty seeded."))
''')
    _shell(base, "AuroraRealty", "A", "listing_new", "List", "keys, viewings, close.",
           "aurora", "  --bg:#0c1014; --bg-2:#141c22; --surface:#141c22; --surface-2:#1c2830; --ink:#f4efe6; --muted:#b8a990; --line:rgba(212,160,80,.14); --brand:#d4a050; --brand-2:#f0d090; --amber:#f0d090; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#d4a050; --radius:16px; --shadow:0 18px 50px rgba(0,0,0,.35); --font:system-ui,serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Property OS", "Listings that know when they are <em>under offer</em>.",
           "80% floor on offers. Accepting one offer sells the home and declines the rest.",
           [("Live", "Only live homes take viewings."), ("Floor", "No 80% lowballs."), ("Close", "One accepted offer, rest lose."), ("Past", "No retro viewings.")])
    w(base / "templates/app/dashboard.html", page("Pipeline", """
<div class="page-head"><h1>Pipeline</h1><a class="btn btn-primary" href="{% url 'listing_new' %}">New listing</a></div>
<div class="grid grid-3"><div class="card stat"><div class="stat-label">Live</div><div class="stat-value">{{ live }}</div></div>
<div class="card stat"><div class="stat-label">Hold</div><div class="stat-value">{{ hold }}</div></div>
<div class="card stat"><div class="stat-label">Sold</div><div class="stat-value">{{ sold }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.code }}</a></td><td>{{ r.title }}</td><td class="num">৳ {{ r.price }}</td><td>{{ r.get_status_display }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %} {% if r.buyer %}{{ r.buyer }} ৳ {{ r.amount }}{% endif %}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ listing.code }}", """
<div class="card"><h1>{{ listing.title }}</h1>
<p>{{ listing.suburb }} · {{ listing.beds }} beds · ৳ {{ listing.price }} · {{ listing.get_status_display }}</p>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="view">
  <input name="visitor" placeholder="Visitor" class="form-control">
  <input type="datetime-local" name="when" class="form-control mt-1">
  <button class="btn btn-secondary mt-2" type="submit">Book viewing</button></form>
<form method="post" class="mt-2">{% csrf_token %}<input type="hidden" name="act" value="offer">
  <input name="buyer" placeholder="Buyer" class="form-control">
  <input name="amount" placeholder="Amount" class="form-control mt-1">
  <button class="btn btn-primary mt-2" type="submit">Place offer</button></form>
{% for o in listing.offers.all %}
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="accept"><input type="hidden" name="offer" value="{{ o.pk }}">
  {{ o.buyer }} ৳ {{ o.amount }} {{ o.status }} <button class="btn btn-sm btn-primary">Accept</button></form>
{% endfor %}</div>
"""))
    w(base / "templates/app/form.html", page("New listing", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Title</label><input class="form-control" name="title" required></div>
  <div class="form-group"><label class="form-label">Suburb</label><input class="form-control" name="suburb"></div>
  <div class="form-group"><label class="form-label">Price</label><input class="form-control" name="price"></div>
  <div class="form-group"><label class="form-label">Beds</label><input class="form-control" name="beds" value="3"></div>
  <select name="agent" class="form-control">{% for a in agents %}<option value="{{ a.pk }}">{{ a }}</option>{% endfor %}</select>
  <button class="btn btn-primary mt-2" type="submit">Publish</button>
</form></div>
"""))


def _shell(base, title, badge, cta_url, cta, footer, theme, css_vars, kicker, h1, lede, cards, rules=None):
    (base / "templates/app").mkdir(parents=True, exist_ok=True)
    (base / "templates/account").mkdir(parents=True, exist_ok=True)
    w(base / "templates/base.html", base_html(title, badge, cta_url, cta, footer))
    w(base / "templates/app/landing.html", landing(kicker, h1, lede, cards))
    w(base / "templates/account/profile.html", PROFILE_TMPL)
    w(base / "static/css/style.css", css(css_vars))
    w(base / "README.md", readme(title, lede.replace("<em>", "").replace("</em>", ""), rules or lede))
    print(" ", title)


# remaining builders continue in this module
BUILDERS = [build_parcelio, build_aurorarealty]
