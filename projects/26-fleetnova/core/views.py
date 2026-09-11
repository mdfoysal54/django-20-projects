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
