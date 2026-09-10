"""AttendX views — teacher dashboards, the register, and student attendance reports."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CohortForm, JoinForm, RegisterForm, SessionForm
from .models import AttendanceRecord, Cohort, Enrollment, Session, rate_band, student_report


def _teachable(user):
    """Cohorts this user may manage: their own (or all, for staff)."""
    return Cohort.objects.all() if user.is_staff else Cohort.objects.filter(teacher=user)


def index(request):
    if request.user.is_authenticated:
        teaching = _teachable(request.user).annotate(n_students=Count("enrollments", distinct=True),
                                                     n_sessions=Count("sessions", distinct=True))
        learning = Cohort.objects.filter(enrollments__student=request.user, enrollments__active=True).distinct()
        return render(request, "attendx/index.html", {
            "teaching": teaching[:6], "learning": learning[:6],
            "recent_sessions": Session.objects.filter(cohort__in=_teachable(request.user))
                                             .order_by("-date")[:5],
            "today_sessions": Session.objects.filter(cohort__in=_teachable(request.user),
                                                     date=timezone.localdate()),
            "report": student_report(request.user),
            "join_form": JoinForm(),
        })
    return render(request, "attendx/index.html", {"public": True, "cohort_count": Cohort.objects.count()})


# -------------------------------------------------------------------- cohorts
@login_required
def cohort_list(request):
    teaching = _teachable(request.user).annotate(n_students=Count("enrollments", distinct=True),
                                                 n_sessions=Count("sessions", distinct=True))
    return render(request, "attendx/cohort_list.html", {"cohorts": teaching})


@login_required
def cohort_create(request):
    if request.method == "POST":
        form = CohortForm(request.POST)
        if form.is_valid():
            cohort = form.save(commit=False)
            cohort.teacher = request.user
            if Cohort.objects.filter(teacher=request.user, name=cohort.name).exists():
                messages.error(request, "You already have a cohort with that name.")
            else:
                cohort.save()
                messages.success(request, f"{cohort.name} created — share code {cohort.code} with your students.")
                return redirect(cohort)
    else:
        form = CohortForm()
    return render(request, "attendx/cohort_form.html", {"form": form})


@login_required
def cohort_edit(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)
    if not cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No cohort found.")
    if request.method == "POST":
        form = CohortForm(request.POST, instance=cohort)
        if form.is_valid():
            form.save()
            messages.success(request, "Cohort updated.")
            return redirect(cohort)
    else:
        form = CohortForm(instance=cohort)
    return render(request, "attendx/cohort_form.html", {"form": form, "cohort": cohort})


@login_required
def cohort_detail(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)
    if not (cohort.can_be_managed_by(request.user) or cohort.is_enrolled(request.user)):
        from django.http import Http404
        raise Http404("No cohort found.")          # enrolled students and the teacher only
    sessions = cohort.sessions.all()
    return render(request, "attendx/cohort_detail.html", {
        "cohort": cohort,
        "sessions": sessions,
        "is_teacher": cohort.can_be_managed_by(request.user),
        "summary": cohort.attendance_summary() if cohort.can_be_managed_by(request.user) else None,
        "my_records": (AttendanceRecord.objects.filter(student=request.user, session__cohort=cohort)
                       .select_related("session") if cohort.is_enrolled(request.user) else []),
        "session_form": SessionForm(initial={"date": timezone.localdate(), "status": Session.Status.SCHEDULED}),
    })


@login_required
@require_POST
def cohort_join(request):
    form = JoinForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter the code your teacher shared.")
        return redirect("home")
    cohort = Cohort.objects.filter(code=form.cleaned_data["code"]).first()
    if cohort is None:
        messages.error(request, "No cohort matches that code.")
        return redirect("home")
    enrollment, error = cohort.join(request.user)
    if error:
        messages.info(request, error)
    else:
        messages.success(request, f"You joined {cohort.name}.")
    return redirect(cohort)


@login_required
@require_POST
def cohort_remove_student(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)
    if not cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No cohort found.")
    enrollment = get_object_or_404(Enrollment, cohort=cohort, student_id=request.POST.get("student"))
    enrollment.active = False        # keep the history, just unenrol
    enrollment.save(update_fields=["active"])
    messages.success(request, "Student removed from the active roster.")
    return redirect(cohort)


# ------------------------------------------------------------------- sessions
@login_required
def session_create(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)
    if not cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No cohort found.")
    if request.method == "POST":
        form = SessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.cohort = cohort
            if Session.objects.filter(cohort=cohort, date=session.date, topic=session.topic).exists():
                messages.error(request, "That cohort already has a session with the same topic on that date.")
            else:
                session.save()
                messages.success(request, "Session scheduled.")
                return redirect("take_attendance", pk=session.pk)
    else:
        form = SessionForm(initial={"date": timezone.localdate()})
    return render(request, "attendx/session_form.html", {"form": form, "cohort": cohort})


@login_required
def session_detail(request, pk):
    session = get_object_or_404(Session.objects.select_related("cohort"), pk=pk)
    cohort = session.cohort
    is_teacher = cohort.can_be_managed_by(request.user)
    if not (is_teacher or cohort.is_enrolled(request.user)):
        from django.http import Http404
        raise Http404("No session found.")
    return render(request, "attendx/session_detail.html", {
        "session": session, "cohort": cohort, "is_teacher": is_teacher,
        "records": session.records.select_related("student", "marked_by"),
        "counts": session.attendance_counts() if is_teacher else None,
        "my_record": session.records.filter(student=request.user).first(),
    })


@login_required
@require_POST
def session_set_status(request, pk, status):
    session = get_object_or_404(Session.objects.select_related("cohort"), pk=pk)
    if not session.cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No session found.")
    if status not in dict(Session.Status.choices):
        messages.error(request, "Unknown status.")
    else:
        session.status = status
        session.save(update_fields=["status"])
        messages.success(request, f"Session marked {session.get_status_display().lower()}.")
    return redirect(session)


# -------------------------------------------------------------------- register
@login_required
def take_attendance(request, pk):
    session = get_object_or_404(Session.objects.select_related("cohort"), pk=pk)
    if not session.cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No session found.")
    if not session.can_mark():
        messages.warning(request, "You can only take attendance for a session that has been held. "
                                  "Mark it as held first." if session.is_future
                         else "This session has not been held yet — mark it as held first.")
        return redirect(session)

    if request.method == "POST":
        if request.POST.get("action") == "all_present":
            n = session.mark_all_present(marked_by=request.user)
            messages.success(request, f"Marked {n} student(s) present — adjust anyone who wasn't.")
            return redirect("take_attendance", pk=session.pk)
        form = RegisterForm(request.POST, session=session, cohort=session.cohort)
        if form.is_valid():
            saved = 0
            for student, status in form.selections():
                session.mark(student, status, marked_by=request.user)
                saved += 1
            messages.success(request, f"Register saved — {saved} record(s).")
            if request.POST.get("action") == "finish":
                return redirect(session)
            return redirect("take_attendance", pk=session.pk)
        messages.error(request, "Could not read the register.")
    else:
        form = RegisterForm(session=session, cohort=session.cohort)

    existing = {r.student_id: r.status for r in session.records.all()}
    roster = [{"student": e.student, "status": existing.get(e.student_id)}
              for e in session.cohort.enrollments.filter(active=True).select_related("student")]
    return render(request, "attendx/register.html", {
        "session": session, "cohort": session.cohort, "form": form, "roster": roster,
        "counts": session.attendance_counts(),
    })


@login_required
def my_attendance(request):
    report = student_report(request.user)
    records = (AttendanceRecord.objects.filter(student=request.user)
               .select_related("session", "session__cohort").order_by("-session__date")[:40])
    return render(request, "attendx/my_attendance.html", {
        "report": report, "records": records, "join_form": JoinForm(),
    })


@login_required
def report(request, pk):
    """Per-student attendance report for one cohort, worst attendance first."""
    cohort = get_object_or_404(Cohort, pk=pk)
    if not cohort.can_be_managed_by(request.user):
        from django.http import Http404
        raise Http404("No cohort found.")
    summary = cohort.attendance_summary()
    for row in summary["rows"]:
        row["band"] = rate_band(row["rate"])
    held = cohort.sessions.filter(status=Session.Status.HELD).order_by("date")
    lookup = {}
    for record in AttendanceRecord.objects.filter(session__in=held):
        lookup[(record.student_id, record.session_id)] = record
    session_list = list(held)
    grid = []
    for row in summary["rows"]:
        grid.append({
            "student": row["student"], "rate": row["rate"], "band": row["band"],
            "cells": [{"record": lookup.get((row["student"].pk, session.pk)), "session": session}
                      for session in session_list],
        })
    return render(request, "attendx/report.html", {
        "cohort": cohort, "summary": summary, "sessions": session_list, "grid": grid,
    })


@login_required
def profile(request):
    report = student_report(request.user)
    return render(request, "account/profile.html", {
        "teaching": _teachable(request.user).count(),
        "joining": request.user.enrollments.filter(active=True).count(),
        "rate": report["overall_rate"],
        "attended": report["total_attended"],
        "counted": report["total_counted"],
        "join_form": JoinForm(),
    })
