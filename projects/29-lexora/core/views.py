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
