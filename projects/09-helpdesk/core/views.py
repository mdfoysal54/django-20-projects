"""HelpDesk views — customer portal, agent queue, triage and metrics.

Access rules enforced here (and covered by tests):
* a requester sees only their own tickets — anyone else gets a 404;
* internal notes never reach a non-agent page;
* triage (priority/status/assignment) is agent-only.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DepartmentForm, FeedbackForm, ReplyForm, TicketForm, TriageForm
from .models import Department, Feedback, Ticket, TicketEvent, TicketMessage

is_agent = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url="login")


def _visible_messages(ticket, user):
    """Agents see everything; requesters never see internal notes."""
    qs = ticket.messages.select_related("author")
    if not (user.is_authenticated and user.is_staff):
        qs = qs.filter(internal=False)
    return qs


def index(request):
    if request.user.is_authenticated:
        my_open = Ticket.objects.filter(requester=request.user, status__in=[Ticket.Status.OPEN,
                                                                          Ticket.Status.IN_PROGRESS,
                                                                          Ticket.Status.WAITING]).count()
    else:
        my_open = 0
    return render(request, "helpdesk/index.html", {
        "departments": Department.objects.annotate(open_count=Count("tickets", filter=Q(tickets__status__in=["open", "in_progress", "waiting"]))),
        "my_open": my_open,
        "queue_depth": Ticket.objects.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
        "recent_resolved": (Ticket.objects.filter(status=Ticket.Status.RESOLVED)
                            .select_related("department")[:3]),
    })


# ------------------------------------------------------------------ customer
@login_required
def new_ticket(request):
    if request.method == "POST":
        form = TicketForm(request.POST, user=request.user)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user
            ticket.sla_due = timezone.now() + timezone.timedelta(hours=Ticket.SLA_HOURS[ticket.priority])
            ticket.save()
            TicketEvent.objects.create(ticket=ticket, actor=request.user, kind="created",
                                       detail=f"Ticket opened in {ticket.department.name}")
            messages.success(request, f"Ticket {ticket.reference} created — first response due "
                                      f"{ticket.sla_due:%b %d, %H:%M}.")
            return redirect(ticket)
    else:
        form = TicketForm(user=request.user)
    return render(request, "helpdesk/ticket_form.html", {"form": form})


@login_required
def my_tickets(request):
    tickets = (Ticket.objects.filter(requester=request.user)
               .select_related("department", "assignee")
               .annotate(n_messages=Count("messages")))
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        tickets = tickets.filter(Q(subject__icontains=q) | Q(reference__icontains=q) | Q(body__icontains=q))
    if status in dict(Ticket.Status.choices):
        tickets = tickets.filter(status=status)
    paginator = Paginator(tickets, 8)
    return render(request, "helpdesk/my_tickets.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q, "status": status,
        "statuses": Ticket.Status.choices,
    })


@login_required
def ticket_detail(request, reference):
    """Requesters may only view their own ticket; agents may view any."""
    qs = Ticket.objects.select_related("department", "assignee", "requester")
    if request.user.is_staff:
        ticket = get_object_or_404(qs, reference=reference)
    else:
        ticket = get_object_or_404(qs, reference=reference, requester=request.user)

    reply_form = ReplyForm(staff=request.user.is_staff)
    triage_form = TriageForm(ticket=ticket) if request.user.is_staff else None

    if request.method == "POST":
        action = request.POST.get("action", "reply")
        if action == "reply":
            reply_form = ReplyForm(request.POST, staff=request.user.is_staff)
            if reply_form.is_valid():
                ticket.add_message(request.user, reply_form.cleaned_data["body"],
                                   internal=reply_form.cleaned_data.get("internal", False))
                messages.success(request, "Message added.")
                return redirect(ticket)
            messages.error(request, "Your reply needs at least 2 characters.")
        elif action == "triage" and request.user.is_staff:
            return _handle_triage(request, ticket)
        elif action == "reopen":
            ticket.set_status(Ticket.Status.OPEN, request.user)
            messages.success(request, "Ticket reopened.")
            return redirect(ticket)

    return render(request, "helpdesk/ticket_detail.html", {
        "ticket": ticket,
        "ticket_messages": _visible_messages(ticket, request.user),
        "events": ticket.events.select_related("actor") if request.user.is_staff else [],
        "reply_form": reply_form,
        "triage_form": triage_form,
        "is_requester": request.user == ticket.requester,
    })


def _handle_triage(request, ticket):
    form = TriageForm(request.POST, ticket=ticket)
    if form.is_valid():
        data = form.cleaned_data
        if data["priority"] != ticket.priority:
            ticket.set_priority(data["priority"], request.user)
            messages.success(request, f"Priority → {ticket.get_priority_display()}.")
        if data["status"] != ticket.status:
            try:
                ticket.set_status(data["status"], request.user)
                messages.success(request, f"Status → {ticket.get_status_display()}.")
            except ValueError as exc:
                messages.error(request, str(exc))
        if data["assignee"] != ticket.assignee:
            if data["assignee"] is None:
                ticket.assignee = None
                ticket.save(update_fields=["assignee"])
                TicketEvent.objects.create(ticket=ticket, actor=request.user, kind="assigned",
                                           detail="Unassigned")
                messages.success(request, "Ticket unassigned.")
            else:
                ticket.assign_to(data["assignee"])
                messages.success(request, f"Assigned to {data['assignee'].username}.")
        return redirect(ticket)
    messages.error(request, "Triage values were not valid.")
    return redirect(ticket)


@login_required
@require_POST
def give_feedback(request, reference):
    ticket = get_object_or_404(Ticket, reference=reference, requester=request.user)
    if ticket.status not in {Ticket.Status.RESOLVED, Ticket.Status.CLOSED}:
        messages.error(request, "You can rate a ticket once it has been resolved.")
        return redirect(ticket)
    form = FeedbackForm(request.POST)
    if form.is_valid():
        feedback, _ = Feedback.objects.update_or_create(ticket=ticket,
                                                        defaults=form.cleaned_data)
        messages.success(request, f"Thanks — you rated this {feedback.score}/5.")
    else:
        messages.error(request, "Pick a score between 1 and 5.")
    return redirect(ticket)


# --------------------------------------------------------------------- agents
@is_agent
def queue(request):
    tickets = Ticket.objects.select_related("department", "requester", "assignee").annotate(n_messages=Count("messages"))
    status = request.GET.get("status", "active")
    priority = request.GET.get("priority", "")
    assignee = request.GET.get("assignee", "")
    q = request.GET.get("q", "").strip()

    if status == "active":
        tickets = tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
    elif status in dict(Ticket.Status.choices):
        tickets = tickets.filter(status=status)
    if priority in dict(Ticket.Priority.choices):
        tickets = tickets.filter(priority=priority)
    if assignee == "me":
        tickets = tickets.filter(assignee=request.user)
    elif assignee == "unassigned":
        tickets = tickets.filter(assignee__isnull=True)
    if q:
        tickets = tickets.filter(Q(subject__icontains=q) | Q(reference__icontains=q)
                                 | Q(requester__username__icontains=q))

    order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    tickets = sorted(tickets, key=lambda t: (order[t.priority], t.sla_due))[:60]
    return render(request, "helpdesk/queue.html", {
        "tickets": tickets, "status": status, "priority": priority, "assignee": assignee, "q": q,
        "statuses": Ticket.Status.choices, "priorities": Ticket.Priority.choices,
        "unassigned_count": Ticket.objects.filter(assignee__isnull=True)
                                          .exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
        "breached_count": sum(1 for t in tickets if t.is_breached),
    })


@is_agent
@require_POST
def claim(request, reference):
    ticket = get_object_or_404(Ticket, reference=reference)
    if ticket.assignee and ticket.assignee != request.user:
        messages.warning(request, f"{ticket.reference} is already assigned to {ticket.assignee.username}.")
    else:
        ticket.assign_to(request.user)
        messages.success(request, f"You now own {ticket.reference}.")
    return redirect(ticket)


@is_agent
@require_POST
def quick_status(request, reference, status):
    ticket = get_object_or_404(Ticket, reference=reference)
    try:
        ticket.set_status(status, request.user)
        messages.success(request, f"{ticket.reference} → {ticket.get_status_display()}.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get("next") or ticket)


@is_agent
def metrics(request):
    now = timezone.now()
    all_tickets = Ticket.objects.all()
    open_qs = all_tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED])
    responded = all_tickets.filter(first_response_at__isnull=False)
    avg_minutes = responded.aggregate(
        avg=Avg(F("first_response_at") - F("created")))["avg"]
    by_status = {row["status"]: row["n"] for row in all_tickets.values("status").annotate(n=Count("id"))}
    by_priority = {row["priority"]: row["n"] for row in open_qs.values("priority").annotate(n=Count("id"))}
    return render(request, "helpdesk/metrics.html", {
        "total": all_tickets.count(),
        "open_count": open_qs.count(),
        "unassigned": open_qs.filter(assignee__isnull=True).count(),
        "breached": sum(1 for t in open_qs if t.is_breached),
        "resolved_today": all_tickets.filter(resolved_at__date=now.date()).count(),
        "avg_first_response_minutes": round(avg_minutes.total_seconds() / 60) if avg_minutes else None,
        "by_status": [
            {"label": dict(Ticket.Status.choices)[k], "key": k, "n": v,
             "pct": round(100 * v / max(all_tickets.count(), 1))}
            for k, v in by_status.items()
        ],
        "by_priority": [
            {"label": dict(Ticket.Priority.choices)[k], "key": k, "n": v}
            for k, v in by_priority.items()
        ],
        "csat": Feedback.objects.aggregate(avg=Avg("score"))["avg"],
        "recent": all_tickets.select_related("requester", "department")[:8],
    })


@is_agent
def departments(request):
    form = DepartmentForm()
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Department added.")
            return redirect("departments")
    return render(request, "helpdesk/departments.html", {
        "form": form,
        "departments": Department.objects.annotate(
            open_count=Count("tickets", filter=Q(tickets__status__in=["open", "in_progress", "waiting"])),
            total=Count("tickets")),
    })


@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "opened": request.user.tickets.count(),
        "open_count": request.user.tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count(),
        "is_agent": request.user.is_staff,
        "assigned": request.user.assigned_tickets.exclude(status__in=[Ticket.Status.RESOLVED, Ticket.Status.CLOSED]).count()
        if request.user.is_staff else 0,
    })
