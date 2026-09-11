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
