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
