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
