"""DevJobs views.

Access rules:
  * browsing jobs is public (open + not expired);
  * applying requires login; one application per (candidate, job) is enforced
    in the view *and* by a DB unique constraint (won't be defeated by race);
  * employer tools (post/edit job, review applicants) are scoped to the
    posting recruiter: get_object_or_404(Job, …, posted_by=request.user).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ApplicationForm, ApplicationStatusForm, CompanyForm, JobForm
from .models import Application, Company, Job, SavedJob

REMOTE_FILTERS = {
    "remote": Job.Remote.REMOTE,
    "hybrid": Job.Remote.HYBRID,
    "onsite": Job.Remote.ONSITE,
}


def _open_jobs(user=None):
    """Open jobs; logged-in recruiters additionally see their own drafts/closed posts."""
    qs = Job.objects.select_related("company").annotate(n_apps=Count("applications"))
    if user is not None and user.is_authenticated:
        return qs.filter(Q(status=Job.Status.OPEN) | Q(posted_by=user))
    return qs.filter(status=Job.Status.OPEN)


def _apply_search(qs, request):
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(tags__icontains=q)
            | Q(company__name__icontains=q)
        )
    location = request.GET.get("location", "").strip()
    if location:
        qs = qs.filter(location__icontains=location)
    job_type = request.GET.get("job_type", "")
    if job_type in Job.Type.values:
        qs = qs.filter(job_type=job_type)
    level = request.GET.get("level", "")
    if level in Job.Level.values:
        qs = qs.filter(level=level)
    remote = request.GET.get("remote", "")
    if remote in REMOTE_FILTERS:
        qs = qs.filter(remote=REMOTE_FILTERS[remote])
    return qs


# ------------------------------------------------------------------ public
def index(request):
    jobs = _open_jobs(request.user).filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate())
    )
    featured = jobs[:6]
    stats = {
        "jobs": Job.objects.filter(status=Job.Status.OPEN).count(),
        "companies": Company.objects.count(),
        "applications": Application.objects.count(),
        "remote": Job.objects.filter(status=Job.Status.OPEN, remote=Job.Remote.REMOTE).count(),
    }
    companies = Company.objects.annotate(n_open=Count("jobs", filter=Q(jobs__status=Job.Status.OPEN))).order_by("-n_open")[:6]
    return render(request, "jobs/index.html", {"featured": featured, "stats": stats, "companies": companies})


def job_list(request):
    jobs = _open_jobs(request.user)
    jobs = _apply_search(jobs, request)
    sort = request.GET.get("sort", "newest")
    if sort == "salary":
        jobs = jobs.order_by("-salary_max", "-created")
    elif sort == "applications":
        jobs = jobs.order_by("-n_apps")
    else:
        jobs = jobs.order_by("-created")
    return render(request, "jobs/job_list.html", {
        "jobs": jobs,
        "sort": sort,
        "job_types": Job.Type.choices,
        "levels": Job.Level.choices,
        "query": request.GET.get("q", ""),
        "location": request.GET.get("location", ""),
        "job_type": request.GET.get("job_type", ""),
        "level": request.GET.get("level", ""),
        "remote": request.GET.get("remote", ""),
    })


def job_detail(request, slug):
    job = get_object_or_404(_open_jobs(request.user), slug=slug)
    existing = None
    saved = False
    if request.user.is_authenticated:
        existing = Application.objects.filter(job=job, applicant=request.user).first()
        saved = SavedJob.objects.filter(job=job, user=request.user).exists()
    similar = (
        Job.objects.filter(status=Job.Status.OPEN, company=job.company)
        .exclude(pk=job.pk)[:3]
    )
    return render(request, "jobs/job_detail.html", {
        "job": job, "existing_application": existing, "saved": saved, "similar": similar,
    })


def company_detail(request, slug):
    company = get_object_or_404(Company, slug=slug)
    jobs = company.jobs.filter(status=Job.Status.OPEN)
    return render(request, "jobs/company_detail.html", {"company": company, "jobs": jobs})


# ------------------------------------------------------------------ applying
@login_required
def apply_job(request, slug):
    job = get_object_or_404(Job, slug=slug)
    if not job.is_open:
        messages.error(request, "This job is no longer accepting applications.")
        return redirect(job)
    if job.posted_by_id == request.user.id:
        messages.info(request, "You posted this job — you can't apply to it.")
        return redirect(job)
    if Application.objects.filter(job=job, applicant=request.user).exists():
        messages.info(request, "You have already applied to this job.")
        return redirect(job)

    if request.method == "POST":
        form = ApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    application = form.save(commit=False)
                    application.job = job
                    application.applicant = request.user
                    application.save()
            except ValidationError:
                messages.error(request, "That application already exists.")
                return redirect(job)
            messages.success(request, f"Application sent to {job.company.name}. Good luck! 🍀")
            return redirect("my_applications")
    else:
        form = ApplicationForm()
    return render(request, "jobs/apply.html", {"job": job, "form": form})


@login_required
def my_applications(request):
    applications = request.user.applications.select_related("job", "job__company")
    return render(request, "jobs/my_applications.html", {"applications": applications})


@login_required
@require_POST
def withdraw_application(request, pk):
    application = get_object_or_404(Application, pk=pk, applicant=request.user)
    if not application.is_active:
        messages.error(request, "This application is already closed.")
        return redirect("my_applications")
    application.withdraw()
    messages.success(request, f"Application withdrawn from {application.job.title}.")
    return redirect("my_applications")


# ------------------------------------------------------------------ saved jobs
@login_required
@require_POST
def toggle_save(request, slug):
    job = get_object_or_404(Job, slug=slug)
    saved, created = SavedJob.objects.get_or_create(user=request.user, job=job)
    if not created:
        saved.delete()
        messages.info(request, "Removed from your saved jobs.")
    else:
        messages.success(request, "Saved for later.")
    return redirect(job)


@login_required
def saved_jobs(request):
    saves = request.user.saved_jobs.select_related("job", "job__company")
    return render(request, "jobs/saved_jobs.html", {"saves": saves})


# ------------------------------------------------------------------ employer
@login_required
def dashboard(request):
    companies = request.user.companies.annotate(n_jobs=Count("jobs"))
    jobs = (
        Job.objects.filter(posted_by=request.user)
        .select_related("company")
        .annotate(n_apps=Count("applications"),
                  n_new=Count("applications", filter=Q(applications__status=Application.Status.SUBMITTED)))
        .order_by("-created")
    )
    return render(request, "jobs/dashboard.html", {"companies": companies, "jobs": jobs})


@login_required
def company_create(request):
    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.owner = request.user
            company.save()
            messages.success(request, "Company profile created — post your first job!")
            return redirect("job_create")
    else:
        form = CompanyForm()
    return render(request, "jobs/company_form.html", {"form": form})


@login_required
def job_create(request):
    companies = request.user.companies.all()
    if not companies.exists():
        messages.info(request, "Create a company profile first.")
        return redirect("company_create")
    if request.method == "POST":
        form = JobForm(request.POST)
        # Only companies owned by the requester are selectable — never trust the POSTed pk.
        company = get_object_or_404(Company, pk=request.POST.get("company") or companies.first().pk, owner=request.user)
        if form.is_valid():
            job = form.save(commit=False)
            job.company = company
            job.posted_by = request.user
            job.status = Job.Status.OPEN
            job.save()
            messages.success(request, "Job published! Applications will appear in your dashboard.")
            return redirect(job)
    else:
        form = JobForm()
    return render(request, "jobs/job_form.html", {"form": form, "companies": companies, "mode": "create"})


@login_required
def job_edit(request, slug):
    job = get_object_or_404(Job, slug=slug, posted_by=request.user)   # recruiter-scoped
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle_open":
            job.status = Job.Status.CLOSED if job.status == Job.Status.OPEN else Job.Status.OPEN
            job.save(update_fields=["status", "updated"])
            messages.success(request, f"Job is now {job.get_status_display().lower()}.")
            return redirect("job_edit", slug=job.slug)
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated.")
            return redirect(job)
    else:
        form = JobForm(instance=job)
    return render(request, "jobs/job_form.html", {"form": form, "job": job, "mode": "edit"})


@login_required
def job_applicants(request, slug):
    job = get_object_or_404(Job, slug=slug, posted_by=request.user)   # recruiter-scoped
    applications = (
        job.applications.select_related("applicant")
        .order_by("status", "-created")
    )
    return render(request, "jobs/job_applicants.html", {"job": job, "applications": applications})


@login_required
def application_review(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("job", "applicant"), pk=pk, job__posted_by=request.user
    )
    if request.method == "POST":
        form = ApplicationStatusForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated {application.applicant.username}'s application.")
            return redirect("job_applicants", slug=application.job.slug)
    else:
        form = ApplicationStatusForm(instance=application)
    return render(request, "jobs/application_review.html", {"application": application, "form": form})


# ------------------------------------------------------------------ account
@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "applications": request.user.applications.count(),
        "saved": request.user.saved_jobs.count(),
        "posted": request.user.jobs_posted.count(),
    })
