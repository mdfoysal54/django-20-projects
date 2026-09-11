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
