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
