"""AetherHR views."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Announcement, Applicant, Asset, Company, Department, Employee, JobPosting,
    LeaveRequest, LeaveType, Payslip, Profile, Punch, Review,
)
from .services import (
    DomainError, advance_applicant, clock_in, clock_out, decide_leave, request_leave,
    run_payroll,
)

NAV = [
    ("People", [("dashboard", "Dashboard"), ("people", "Directory"), ("org", "Org chart")]),
    ("Time", [("clock", "Clock"), ("leave_list", "Leave"), ("payroll", "Payroll")]),
    ("Talent", [("jobs", "Recruiting"), ("reviews", "Reviews"), ("assets", "Assets"), ("news", "News")]),
    ("Reports", [("report_headcount", "Headcount"), ("report_leave", "Leave balance")]),
]


def _ctx(request, **extra):
    extra.setdefault("company", Company.get())
    extra.setdefault("nav", NAV)
    extra.setdefault("today", timezone.localdate())
    extra.setdefault("me", getattr(request.user, "employee", None) if request.user.is_authenticated else None)
    return extra


def _employee(user):
    return getattr(user, "employee", None)


def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "hr/landing.html", _ctx(request))


@login_required
def dashboard(request):
    people = Employee.objects.filter(status=Employee.Status.ACTIVE)
    pending = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
    return render(request, "hr/dashboard.html", _ctx(request,
        n_people=people.count(), pending=pending.count(),
        news=Announcement.objects.order_by("-published_on")[:5],
        punches=Punch.objects.filter(day=timezone.localdate()).select_related("employee__user")[:12],
    ))


@login_required
def people(request):
    rows = Employee.objects.select_related("user", "department", "designation")
    q = request.GET.get("q", "").strip()
    if q:
        rows = rows.filter(user__first_name__icontains=q) | rows.filter(code__icontains=q)
    return render(request, "hr/people.html", _ctx(request, rows=rows, q=q))


@login_required
def employee_detail(request, code):
    emp = get_object_or_404(Employee.objects.select_related("user", "department", "designation", "manager"), code=code)
    return render(request, "hr/employee.html", _ctx(request, emp=emp,
        slips=emp.payslips.all()[:6], leaves=emp.leaves.all()[:6], assets=emp.assets.all()))


@login_required
def org(request):
    roots = Employee.objects.filter(manager__isnull=True, status=Employee.Status.ACTIVE).select_related("user")
    return render(request, "hr/org.html", _ctx(request, roots=roots))


@login_required
def clock(request):
    me = _employee(request.user)
    if request.method == "POST" and me:
        try:
            if request.POST.get("intent") == "in":
                clock_in(me)
                messages.success(request, "Clocked in.")
            else:
                clock_out(me)
                messages.success(request, "Clocked out.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect("clock")
    today = Punch.objects.filter(employee=me, day=timezone.localdate()).first() if me else None
    history = Punch.objects.filter(employee=me).order_by("-day")[:14] if me else []
    return render(request, "hr/clock.html", _ctx(request, today=today, history=history))


@login_required
def leave_list(request):
    rows = LeaveRequest.objects.select_related("employee__user", "kind")
    return render(request, "hr/leaves.html", _ctx(request, rows=rows))


@login_required
def leave_new(request):
    me = _employee(request.user)
    if me is None:
        messages.error(request, "Only employees can request leave.")
        return redirect("leave_list")
    if request.method == "POST":
        try:
            kind = get_object_or_404(LeaveType, pk=request.POST.get("kind"))
            req = request_leave(me, kind, timezone.datetime.fromisoformat(request.POST["starts"]).date(),
                                timezone.datetime.fromisoformat(request.POST["ends"]).date(),
                                request.POST.get("reason") or "")
            messages.success(request, "Leave requested.")
            return redirect(req)
        except (DomainError, ValueError, KeyError) as exc:
            messages.error(request, str(exc))
    return render(request, "hr/leave_form.html", _ctx(request, kinds=LeaveType.objects.all()))


@login_required
def leave_detail(request, pk):
    req = get_object_or_404(LeaveRequest, pk=pk)
    return render(request, "hr/leave.html", _ctx(request, req=req))


@login_required
@require_POST
def leave_decide(request, pk):
    req = get_object_or_404(LeaveRequest, pk=pk)
    try:
        decide_leave(req, request.POST.get("intent") == "ok", request.user)
        messages.success(request, f"Leave {req.get_status_display().lower()}.")
    except DomainError as exc:
        messages.error(request, str(exc))
    return redirect(req)


@login_required
def payroll(request):
    period = request.POST.get("period") or timezone.localdate().strftime("%Y-%m")
    if request.method == "POST" and request.POST.get("intent") == "run":
        n = 0
        for emp in Employee.objects.filter(status=Employee.Status.ACTIVE):
            unpaid = int(request.POST.get(f"u_{emp.pk}") or 0)
            run_payroll(emp, period, unpaid)
            n += 1
        messages.success(request, f"Payroll {period} posted for {n} people.")
        return redirect("payroll")
    slips = Payslip.objects.filter(period=period).select_related("employee__user")
    return render(request, "hr/payroll.html", _ctx(
        request, period=period, slips=slips,
        people=Employee.objects.filter(status=Employee.Status.ACTIVE).select_related("user"),
    ))


@login_required
def payslip_detail(request, pk):
    slip = get_object_or_404(Payslip, pk=pk)
    return render(request, "hr/payslip.html", _ctx(request, slip=slip))


@login_required
def jobs(request):
    if request.method == "POST":
        dept = get_object_or_404(Department, pk=request.POST.get("department"))
        JobPosting.objects.create(title=request.POST.get("title") or "Role",
                                  department=dept, body=request.POST.get("body") or "")
        messages.success(request, "Job posted.")
        return redirect("jobs")
    return render(request, "hr/jobs.html", _ctx(request, jobs=JobPosting.objects.select_related("department"),
                                                departments=Department.objects.all()))


@login_required
def job_detail(request, pk):
    job = get_object_or_404(JobPosting, pk=pk)
    if request.method == "POST":
        Applicant.objects.get_or_create(job=job, email=request.POST.get("email"),
                                        defaults={"name": request.POST.get("name") or "Applicant"})
        messages.success(request, "Applicant recorded.")
        return redirect(job)
    return render(request, "hr/job.html", _ctx(request, job=job, applicants=job.applicants.all()))


@login_required
@require_POST
def applicant_advance(request, pk, app):
    applicant = get_object_or_404(Applicant, pk=app, job_id=pk)
    try:
        advance_applicant(applicant)
        messages.success(request, f"{applicant.name} → {applicant.get_stage_display()}.")
    except DomainError as exc:
        messages.error(request, str(exc))
    return redirect("job_detail", pk=pk)


@login_required
def reviews(request):
    if request.method == "POST":
        emp = get_object_or_404(Employee, pk=request.POST.get("employee"))
        rating = int(request.POST.get("rating") or 3)
        rating = max(1, min(5, rating))
        Review.objects.update_or_create(employee=emp, period=request.POST.get("period") or timezone.localdate().strftime("%Y-%m"),
                                        defaults={"rating": rating, "goals": request.POST.get("goals") or "",
                                                  "notes": request.POST.get("notes") or "", "reviewer": request.user})
        messages.success(request, "Review saved.")
        return redirect("reviews")
    return render(request, "hr/reviews.html", _ctx(
        request, rows=Review.objects.select_related("employee__user"),
        people=Employee.objects.filter(status=Employee.Status.ACTIVE)))


@login_required
def assets(request):
    if request.method == "POST":
        Asset.objects.create(name=request.POST.get("name") or "Asset",
                             tag=request.POST.get("tag") or timezone.now().strftime("A%H%M%S"),
                             assigned_to=Employee.objects.filter(pk=request.POST.get("employee")).first(),
                             cost=Decimal(request.POST.get("cost") or "0"))
        messages.success(request, "Asset saved.")
        return redirect("assets")
    return render(request, "hr/assets.html", _ctx(request, rows=Asset.objects.select_related("assigned_to__user"),
                                                  people=Employee.objects.all()))


@login_required
def news(request):
    if request.method == "POST":
        Announcement.objects.create(title=request.POST.get("title") or "Update",
                                    body=request.POST.get("body") or "", author=request.user)
        messages.success(request, "Published.")
        return redirect("news")
    return render(request, "hr/news.html", _ctx(request, rows=Announcement.objects.all()))


@login_required
def report_headcount(request):
    depts = Department.objects.all()
    rows = [(d, d.people.filter(status=Employee.Status.ACTIVE).count()) for d in depts]
    return render(request, "hr/report.html", _ctx(request, title="Headcount", rows=rows, kind="hc"))


@login_required
def report_leave(request):
    from .models import LeaveBalance
    rows = LeaveBalance.objects.select_related("employee__user", "kind")
    return render(request, "hr/report.html", _ctx(request, title="Leave balances", rows=rows, kind="leave"))


@login_required
def settings_hub(request):
    company = Company.get()
    if request.method == "POST":
        company.name = request.POST.get("name") or company.name
        company.theme = request.POST.get("theme") or company.theme
        company.language = request.POST.get("language") or company.language
        company.save()
        messages.success(request, "Company saved.")
        return redirect("settings_hub")
    return render(request, "hr/settings.html", _ctx(request, company=company))


@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        profile.theme = request.POST.get("theme") or profile.theme
        profile.language = request.POST.get("language") or profile.language
        profile.phone = request.POST.get("phone") or ""
        profile.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "account/profile.html", _ctx(request, profile=profile))
