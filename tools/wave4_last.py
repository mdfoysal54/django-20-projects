"""Wave-4 builders 27–29: OrbitPay, PulseGrid, Lexora."""
from __future__ import annotations

from wave4_build import page, profile_view, seed_users, urls, w
from wave4_rest import _shell


def build_orbitpay(base):
    w(base / "core/models.py", '''
"""OrbitPay — wallets, transfers, ledgers."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    handle = models.SlugField(unique=True)
    currency = models.CharField(max_length=3, default="BDT")
    def __str__(self):
        return f"@{self.handle}"
    def get_absolute_url(self):
        return reverse("account_detail", kwargs={"handle": self.handle})

class Transfer(models.Model):
    class Status(models.TextChoices):
        POSTED = "post", "Posted"
        VOID = "void", "Void"
    number = models.CharField(max_length=22, unique=True, editable=False)
    src = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="out_transfers")
    dst = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="in_transfers")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    memo = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.POSTED)
    created = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Transfer.objects.filter(number__startswith=f"PAY-{day}").count() + 1
            self.number = f"PAY-{day}-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("transfer_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Entry(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="entries")
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="entries")
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # signed
    def __str__(self):
        return f"{self.account} {self.amount}"
''')
    w(base / "core/services.py", '''
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from .models import Account, Entry, Transfer

class DomainError(ValueError):
    pass

def balance(account) -> Decimal:
    return account.entries.aggregate(s=Sum("amount"))["s"] or Decimal("0")

@transaction.atomic
def credit(account, amount, memo="seed"):
    if amount <= 0:
        raise DomainError("Credit must be positive.")
    t = Transfer.objects.create(src=account, dst=account, amount=amount, memo=memo)
    Entry.objects.create(account=account, transfer=t, amount=amount)
    return t

@transaction.atomic
def send(*, src, dst, amount, memo=""):
    amount = Decimal(str(amount))
    if src.pk == dst.pk:
        raise DomainError("Cannot pay yourself.")
    if amount <= 0:
        raise DomainError("Amount must be positive.")
    if balance(src) < amount:
        raise DomainError("Insufficient funds.")
    t = Transfer.objects.create(src=src, dst=dst, amount=amount, memo=memo)
    Entry.objects.create(account=src, transfer=t, amount=-amount)
    Entry.objects.create(account=dst, transfer=t, amount=amount)
    return t

@transaction.atomic
def void_transfer(t):
    if t.status == Transfer.Status.VOID:
        raise DomainError("Already void.")
    if t.src_id == t.dst_id:
        raise DomainError("Seed credits cannot be voided.")
    t.status = Transfer.Status.VOID
    t.save()
    Entry.objects.create(account=t.src, transfer=t, amount=t.amount)
    Entry.objects.create(account=t.dst, transfer=t, amount=-t.amount)
    return t
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Account, Transfer
from .services import DomainError, balance, send, void_transfer

NAV = [("Money", [("dashboard", "Orbit"), ("transfer_list", "Ledger"), ("transfer_new", "Send")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    acct = Account.objects.filter(user=request.user).first()
    return render(request, "app/dashboard.html", _ctx(request, acct=acct,
        bal=balance(acct) if acct else 0,
        rows=Transfer.objects.select_related("src", "dst").order_by("-id")[:20]))

@login_required
def transfer_list(request):
    return render(request, "app/list.html", _ctx(request, title="Ledger",
        rows=Transfer.objects.select_related("src", "dst"), kind="pay"))

@login_required
def transfer_detail(request, number):
    t = get_object_or_404(Transfer, number=number)
    if request.method == "POST":
        try:
            void_transfer(t)
            messages.success(request, "Voided.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(t)
    return render(request, "app/detail.html", _ctx(request, t=t))

@login_required
def transfer_new(request):
    src = get_object_or_404(Account, user=request.user)
    if request.method == "POST":
        try:
            dst = get_object_or_404(Account, handle=request.POST.get("handle"))
            t = send(src=src, dst=dst, amount=request.POST.get("amount") or 0, memo=request.POST.get("memo") or "")
            return redirect(t)
        except DomainError as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, src=src, bal=balance(src)))

@login_required
def account_detail(request, handle):
    acct = get_object_or_404(Account, handle=handle)
    return render(request, "app/detail.html", _ctx(request, acct=acct, bal=balance(acct), kind="acct"))
''' + profile_view())
    w(base / "core/urls.py", urls("OrbitPay", '''
    path("ledger/", views.transfer_list, name="transfer_list"),
    path("send/", views.transfer_new, name="transfer_new"),
    path("pay/<str:number>/", views.transfer_detail, name="transfer_detail"),
    path("@<slug:handle>/", views.account_detail, name="account_detail"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Account, models.Transfer, models.Entry):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Account
from .services import DomainError, balance, credit, send, void_transfer

class PayTests(TestCase):
    def setUp(self):
        self.a = Account.objects.create(user=User.objects.create_user("a", password="x"), handle="alice")
        self.b = Account.objects.create(user=User.objects.create_user("b", password="x"), handle="bob")
        credit(self.a, 1000)
    def test_overdraft(self):
        with self.assertRaises(DomainError):
            send(src=self.a, dst=self.b, amount=5000)
    def test_self_pay(self):
        with self.assertRaises(DomainError):
            send(src=self.a, dst=self.a, amount=10)
    def test_void_restores(self):
        t = send(src=self.a, dst=self.b, amount=250)
        self.assertEqual(balance(self.a), 750)
        void_transfer(t)
        self.assertEqual(balance(self.a), 1000)
        self.assertEqual(balance(self.b), 0)
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
from core.models import Account, Transfer
from core.services import credit, send

class Command(BaseCommand):
    help = "Seed OrbitPay."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        alice = User.objects.get(username="alice")
        admin = User.objects.get(username="admin")
        aa, _ = Account.objects.get_or_create(user=alice, defaults={{"handle": "alice"}})
        ab, _ = Account.objects.get_or_create(user=admin, defaults={{"handle": "orbit"}})
        if not Transfer.objects.exists():
            credit(aa, 50000, "genesis")
            send(src=aa, dst=ab, amount=1200, memo="demo")
        self.stdout.write(self.style.SUCCESS("OrbitPay seeded."))
''')
    _shell(base, "OrbitPay", "O", "transfer_new", "Send", "double-entry, always.",
           "void", "  --bg:#05060c; --bg-2:#0c1220; --surface:#0c1220; --surface-2:#121a2c; --ink:#e8f4ff; --muted:#7aa0c0; --line:rgba(80,200,255,.14); --brand:#3ec8ff; --brand-2:#7cf7ff; --amber:#d0ff5e; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#3ec8ff; --radius:16px; --shadow:0 18px 50px rgba(0,0,0,.45); --font:system-ui,sans-serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Payments OS", "Wallets with a ledger that <em>never</em> overdrafts.",
           "Every send is two entries. Voids reverse both. No self-pay.",
           [("Wallets", "One per user."), ("Send", "Balance checked."), ("Void", "Reversing entries."), ("Seed", "Genesis credits.")],
           "- Cannot pay yourself.\n- Insufficient funds refused.\n- Void writes reversing ledger lines.")
    w(base / "templates/app/dashboard.html", page("Orbit", """
<div class="page-head"><h1>@{{ acct.handle }}</h1><a class="btn btn-primary" href="{% url 'transfer_new' %}">Send</a></div>
<div class="card stat"><div class="stat-label">Balance</div><div class="stat-value num">৳ {{ bal }}</div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.src }} → {{ r.dst }}</td><td class="num">{{ r.amount }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r }}</a></td><td>{{ r.src }} → {{ r.dst }} · {{ r.amount }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("Pay", """
{% if t %}
<div class="card"><h1>{{ t.number }}</h1>
<p>{{ t.src }} → {{ t.dst }} · ৳ {{ t.amount }} · {{ t.get_status_display }}</p>
<form method="post">{% csrf_token %}<button class="btn btn-danger">Void</button></form></div>
{% else %}
<div class="card"><h1>@{{ acct.handle }}</h1><p class="stat-value">৳ {{ bal }}</p></div>
{% endif %}
"""))
    w(base / "templates/app/form.html", page("Send", """
<div class="card"><p class="muted">Balance ৳ {{ bal }}</p>
<form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">To handle</label><input class="form-control" name="handle" placeholder="orbit" required></div>
  <div class="form-group"><label class="form-label">Amount</label><input class="form-control" name="amount" required></div>
  <input class="form-control" name="memo" placeholder="Memo">
  <button class="btn btn-primary mt-2">Transmit</button>
</form></div>
"""))


def build_pulsegrid(base):
    w(base / "core/models.py", '''
"""PulseGrid — sites, incidents, on-call."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Site(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self):
        return self.name

class Monitor(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="monitors")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=16, default="http")
    class Meta:
        unique_together = ("site", "name")
    def __str__(self):
        return f"{self.site}:{self.name}"

class Incident(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACK = "ack", "Acknowledged"
        RES = "res", "Resolved"
    number = models.CharField(max_length=20, unique=True, editable=False)
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="incidents")
    title = models.CharField(max_length=140)
    severity = models.CharField(max_length=8, default="sev2")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            n = Incident.objects.count() + 1
            self.number = f"INC-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("incident_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class OnCall(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="oncall")
    name = models.CharField(max_length=80)
    def __str__(self):
        return f"{self.site} → {self.name}"
''')
    w(base / "core/services.py", '''
from django.db import transaction
from .models import Incident

class DomainError(ValueError):
    pass

@transaction.atomic
def page_incident(*, monitor, title, severity="sev2"):
    open_same = Incident.objects.filter(monitor=monitor, status__in=("open", "ack"), title=title)
    if open_same.exists():
        raise DomainError("An open incident already covers this signal.")
    return Incident.objects.create(monitor=monitor, title=title, severity=severity)

@transaction.atomic
def ack(incident):
    if incident.status != Incident.Status.OPEN:
        raise DomainError("Only open incidents can be acked.")
    incident.status = Incident.Status.ACK
    incident.save(update_fields=["status"])
    return incident

@transaction.atomic
def resolve(incident):
    if incident.status == Incident.Status.RES:
        raise DomainError("Already resolved.")
    incident.status = Incident.Status.RES
    incident.save(update_fields=["status"])
    return incident
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Incident, Monitor, OnCall, Site
from .services import DomainError, ack, page_incident, resolve

NAV = [("Grid", [("dashboard", "Pulse"), ("incident_list", "Incidents"), ("incident_new", "Page")]),
       ("Sites", [("site_list", "Sites")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Incident.objects.select_related("monitor__site")
    return render(request, "app/dashboard.html", _ctx(request, rows=qs.order_by("-id")[:30],
        open=qs.filter(status="open").count(), ack=qs.filter(status="ack").count()))

@login_required
def incident_list(request):
    return render(request, "app/list.html", _ctx(request, title="Incidents",
        rows=Incident.objects.select_related("monitor__site"), kind="inc"))

@login_required
def incident_detail(request, number):
    inc = get_object_or_404(Incident, number=number)
    if request.method == "POST":
        try:
            if request.POST.get("act") == "ack":
                ack(inc)
            else:
                resolve(inc)
            messages.success(request, "Updated.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(inc)
    return render(request, "app/detail.html", _ctx(request, inc=inc))

@login_required
def incident_new(request):
    if request.method == "POST":
        try:
            mon = get_object_or_404(Monitor, pk=request.POST.get("monitor"))
            inc = page_incident(monitor=mon, title=request.POST.get("title") or "Signal",
                                severity=request.POST.get("sev") or "sev2")
            return redirect(inc)
        except DomainError as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, monitors=Monitor.objects.select_related("site")))

@login_required
def site_list(request):
    return render(request, "app/list.html", _ctx(request, title="Sites", rows=Site.objects.all(), kind="site"))
''' + profile_view())
    w(base / "core/urls.py", urls("PulseGrid", '''
    path("incidents/", views.incident_list, name="incident_list"),
    path("incidents/new/", views.incident_new, name="incident_new"),
    path("incidents/<str:number>/", views.incident_detail, name="incident_detail"),
    path("sites/", views.site_list, name="site_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Site, models.Monitor, models.Incident, models.OnCall):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Monitor, Site
from .services import DomainError, ack, page_incident, resolve

class GridTests(TestCase):
    def setUp(self):
        s = Site.objects.create(name="api", slug="api")
        self.m = Monitor.objects.create(site=s, name="latency")
    def test_dedupe(self):
        page_incident(monitor=self.m, title="p99")
        with self.assertRaises(DomainError):
            page_incident(monitor=self.m, title="p99")
    def test_ack_then_resolve(self):
        inc = page_incident(monitor=self.m, title="5xx")
        ack(inc)
        with self.assertRaises(DomainError):
            ack(inc)
        resolve(inc)
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
from core.models import Incident, Monitor, OnCall, Site
from core.services import page_incident

class Command(BaseCommand):
    help = "Seed PulseGrid."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        s, _ = Site.objects.get_or_create(slug="edge", defaults={{"name": "edge-dhaka"}})
        OnCall.objects.get_or_create(site=s, defaults={{"name": "Alice Rahman"}})
        m, _ = Monitor.objects.get_or_create(site=s, name="https")
        if not Incident.objects.exists():
            page_incident(monitor=m, title="TLS handshake spike", severity="sev2")
        self.stdout.write(self.style.SUCCESS("PulseGrid seeded."))
''')
    _shell(base, "PulseGrid", "G", "incident_new", "Page", "signals without duplicates.",
           "void", "  --bg:#050805; --bg-2:#0c140c; --surface:#0c140c; --surface-2:#142014; --ink:#d8ffd8; --muted:#7cb07c; --line:rgba(80,255,120,.14); --brand:#39ff14; --brand-2:#b6ff4a; --amber:#d0ff5e; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#39ff14; --radius:12px; --shadow:0 18px 50px rgba(0,0,0,.5); --font:ui-monospace,monospace; --mono:ui-monospace,monospace; --rail:248px;",
           "SRE OS", "Incidents that <em>dedupe</em> themselves.",
           "Same open title on a monitor cannot page twice. Ack only from open.",
           [("Sites", "Named edges."), ("Monitors", "HTTP / latency."), ("Page", "No duplicate opens."), ("Ack", "Then resolve.")],
           "- Duplicate open incidents on the same monitor+title are refused.\n- Ack only from open.\n- Resolve is terminal.")
    w(base / "templates/app/dashboard.html", page("Pulse", """
<div class="page-head"><h1>Grid</h1><a class="btn btn-primary" href="{% url 'incident_new' %}">Page</a></div>
<div class="grid grid-2"><div class="card stat"><div class="stat-label">Open</div><div class="stat-value">{{ open }}</div></div>
<div class="card stat"><div class="stat-label">Acked</div><div class="stat-value">{{ ack }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.monitor }}</td><td>{{ r.title }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td>{{ r.title|default:r.slug|default:"" }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ inc.number }}", """
<div class="card"><h1>{{ inc.number }}</h1>
<p>{{ inc.monitor }} · {{ inc.title }} · {{ inc.get_status_display }}</p>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="ack"><button class="btn btn-secondary">Ack</button></form>
<form method="post">{% csrf_token %}<button class="btn btn-primary">Resolve</button></form></div>
"""))
    w(base / "templates/app/form.html", page("Page", """
<div class="card"><form method="post">{% csrf_token %}
  <select name="monitor" class="form-control">{% for m in monitors %}<option value="{{ m.pk }}">{{ m }}</option>{% endfor %}</select>
  <input name="title" class="form-control mt-1" placeholder="Signal">
  <input name="sev" class="form-control mt-1" value="sev2">
  <button class="btn btn-primary mt-2">Open incident</button>
</form></div>
"""))


def build_lexora(base):
    w(base / "core/models.py", '''
"""Lexora — matters, time, retainers."""
from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Matter(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        BILL = "bill", "Billing"
        CLOSE = "close", "Closed"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    client = models.CharField(max_length=80)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=8000)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    retainer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    def save(self, *a, **k):
        if not self.number:
            n = Matter.objects.count() + 1
            self.number = f"MAT-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("matter_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class TimeEntry(models.Model):
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, related_name="entries")
    minutes = models.PositiveIntegerField()
    note = models.CharField(max_length=200)
    billed = models.BooleanField(default=False)
    at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, related_name="invoices")
    number = models.CharField(max_length=20, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issued = models.DateField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            n = Invoice.objects.count() + 1
            self.number = f"LEX-{n:04d}"
        super().save(*a, **k)
    def __str__(self):
        return self.number
''')
    w(base / "core/services.py", '''
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Sum
from .models import Invoice, TimeEntry

class DomainError(ValueError):
    pass

def unbilled_minutes(matter):
    return matter.entries.filter(billed=False).aggregate(s=Sum("minutes"))["s"] or 0

@transaction.atomic
def log_time(matter, minutes, note):
    if matter.status == matter.Status.CLOSE:
        raise DomainError("Closed matters do not take time.")
    if minutes < 6:
        raise DomainError("Minimum slice is 6 minutes.")
    return TimeEntry.objects.create(matter=matter, minutes=minutes, note=note)

@transaction.atomic
def bill(matter):
    mins = unbilled_minutes(matter)
    if mins == 0:
        raise DomainError("Nothing to bill.")
    hours = Decimal(mins) / Decimal(60)
    amount = (hours * matter.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount > matter.retainer and matter.retainer > 0:
        # draw retainer first; remaining still billed
        pass
    inv = Invoice.objects.create(matter=matter, amount=amount)
    matter.entries.filter(billed=False).update(billed=True)
    if matter.retainer:
        draw = min(matter.retainer, amount)
        matter.retainer -= draw
    matter.status = matter.Status.BILL
    matter.save()
    return inv
''')
    w(base / "core/views.py", '''
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Invoice, Matter
from .services import DomainError, bill, log_time, unbilled_minutes

NAV = [("Practice", [("dashboard", "Chambers"), ("matter_list", "Matters"), ("matter_new", "Open")]),
       ("Books", [("invoice_list", "Invoices")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    qs = Matter.objects.all()
    return render(request, "app/dashboard.html", _ctx(request, rows=qs,
        open=qs.filter(status="open").count(), billed=Invoice.objects.count()))

@login_required
def matter_list(request):
    return render(request, "app/list.html", _ctx(request, title="Matters", rows=Matter.objects.all(), kind="mat"))

@login_required
def matter_detail(request, number):
    matter = get_object_or_404(Matter, number=number)
    if request.method == "POST":
        try:
            if request.POST.get("act") == "time":
                log_time(matter, int(request.POST.get("minutes") or 0), request.POST.get("note") or "work")
            else:
                inv = bill(matter)
                messages.success(request, f"{inv.number} issued.")
        except (DomainError, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(matter)
    return render(request, "app/detail.html", _ctx(request, matter=matter, unbilled=unbilled_minutes(matter)))

@login_required
def matter_new(request):
    if request.method == "POST":
        m = Matter.objects.create(title=request.POST.get("title") or "Matter",
            client=request.POST.get("client") or "Client",
            rate=request.POST.get("rate") or 8000,
            retainer=request.POST.get("retainer") or 0)
        return redirect(m)
    return render(request, "app/form.html", _ctx(request))

@login_required
def invoice_list(request):
    return render(request, "app/list.html", _ctx(request, title="Invoices",
        rows=Invoice.objects.select_related("matter"), kind="inv"))
''' + profile_view())
    w(base / "core/urls.py", urls("Lexora", '''
    path("matters/", views.matter_list, name="matter_list"),
    path("matters/new/", views.matter_new, name="matter_new"),
    path("matters/<str:number>/", views.matter_detail, name="matter_detail"),
    path("invoices/", views.invoice_list, name="invoice_list"),
'''))
    w(base / "core/admin.py", "from django.contrib import admin\\nfrom . import models\\nfor m in (models.Matter, models.TimeEntry, models.Invoice):\\n    admin.site.register(m)\\n")
    w(base / "core/tests.py", '''
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from .models import Matter
from .services import DomainError, bill, log_time

class LexTests(TestCase):
    def setUp(self):
        self.m = Matter.objects.create(title="Share sale", client="Nexora", rate=6000, retainer=10000)
    def test_min_slice(self):
        with self.assertRaises(DomainError):
            log_time(self.m, 3, "call")
    def test_bill(self):
        log_time(self.m, 60, "draft")
        inv = bill(self.m)
        self.assertEqual(inv.amount, 6000)
        with self.assertRaises(DomainError):
            bill(self.m)
    def test_closed(self):
        self.m.status = Matter.Status.CLOSE
        self.m.save()
        with self.assertRaises(DomainError):
            log_time(self.m, 30, "x")
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
from core.models import Matter
from core.services import bill, log_time

class Command(BaseCommand):
    help = "Seed Lexora."
    def add_arguments(self, p): p.add_argument("--force", action="store_true")
    def handle(self, *a, **options):
{seed_users()}
        if not Matter.objects.exists():
            m = Matter.objects.create(title="Series seed round", client="OrbitPay Ltd", rate=9000, retainer=50000)
            log_time(m, 90, "term sheet markup")
            bill(m)
        self.stdout.write(self.style.SUCCESS("Lexora seeded."))
''')
    _shell(base, "Lexora", "L", "matter_new", "Open matter", "time that bills itself.",
           "void", "  --bg:#0b1020; --bg-2:#141c30; --surface:#141c30; --surface-2:#1c2840; --ink:#f4efe4; --muted:#b0a890; --line:rgba(200,180,140,.14); --brand:#e8d5a3; --brand-2:#8aa2c8; --amber:#e8d5a3; --ok:#3dd68c; --warn:#ffb020; --bad:#ff5d73; --info:#8aa2c8; --radius:14px; --shadow:0 18px 50px rgba(0,0,0,.4); --font:ui-serif,Georgia,serif; --mono:ui-monospace,monospace; --rail:248px;",
           "Practice OS", "Matters, six-minute slices, retainers that <em>draw down</em>.",
           "Closed files refuse time. Billing with zero unbilled minutes is refused.",
           [("Matters", "Numbered files."), ("Time", "6-minute minimum."), ("Bill", "Rate × hours."), ("Retainer", "Draws on invoice.")],
           "- Minimum time slice is 6 minutes.\n- Closed matters refuse time.\n- Cannot bill with zero unbilled minutes.")
    w(base / "templates/app/dashboard.html", page("Chambers", """
<div class="page-head"><h1>Chambers</h1><a class="btn btn-primary" href="{% url 'matter_new' %}">Open matter</a></div>
<div class="grid grid-2"><div class="card stat"><div class="stat-label">Open</div><div class="stat-value">{{ open }}</div></div>
<div class="card stat"><div class="stat-label">Invoices</div><div class="stat-value">{{ billed }}</div></div></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td><a href="{{ r.get_absolute_url }}">{{ r.number }}</a></td><td>{{ r.title }} · {{ r.client }}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/list.html", page("{{ title }}", """
<div class="page-head"><h1>{{ title }}</h1></div>
<div class="table-wrap"><table class="tbl"><tbody>{% for r in rows %}<tr><td>{% if r.get_absolute_url %}<a href="{{ r.get_absolute_url }}">{{ r }}</a>{% else %}{{ r }}{% endif %}</td><td>{% if r.amount %}৳ {{ r.amount }}{% else %}{{ r.title|default:"" }}{% endif %}</td></tr>{% endfor %}</tbody></table></div>
"""))
    w(base / "templates/app/detail.html", page("{{ matter.number }}", """
<div class="card"><h1>{{ matter.title }}</h1>
<p>{{ matter.client }} · ৳ {{ matter.rate }}/h · retainer ৳ {{ matter.retainer }} · unbilled {{ unbilled }}m</p>
<form method="post">{% csrf_token %}<input type="hidden" name="act" value="time">
  <input name="minutes" placeholder="Minutes" class="form-control">
  <input name="note" placeholder="Note" class="form-control mt-1">
  <button class="btn btn-secondary mt-2">Log time</button></form>
<form method="post">{% csrf_token %}<button class="btn btn-primary">Issue invoice</button></form>
<ul>{% for e in matter.entries.all %}<li>{{ e.minutes }}m {{ e.note }} {% if e.billed %}billed{% endif %}</li>{% endfor %}</ul>
</div>
"""))
    w(base / "templates/app/form.html", page("Open matter", """
<div class="card"><form method="post">{% csrf_token %}
  <div class="form-group"><label class="form-label">Title</label><input class="form-control" name="title" required></div>
  <input class="form-control" name="client" placeholder="Client">
  <input class="form-control mt-1" name="rate" value="8000">
  <input class="form-control mt-1" name="retainer" value="0">
  <button class="btn btn-primary mt-2">Open</button>
</form></div>
"""))


BUILDERS = [build_orbitpay, build_pulsegrid, build_lexora]
