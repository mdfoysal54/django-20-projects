"""EventTix views — event catalogue, booking flow, organiser tools and door check-in."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BookingForm, CheckInForm, EventForm, TierForm
from .models import Booking, Event, TicketTier


def _visible_events():
    return (Event.objects.exclude(status=Event.Status.DRAFT)
            .select_related("organiser")
            .annotate(capacity=Sum("tiers__capacity"),
                      sold_total=Sum("tiers__sold"),
                      seats_left=Sum(F("tiers__capacity") - F("tiers__sold"))))


def index(request):
    events = _visible_events().filter(starts_at__gte=timezone.now())
    return render(request, "events/index.html", {
        "featured": events.filter(status=Event.Status.ON_SALE).order_by("-created")[:3],
        "events": events.order_by("starts_at")[:6],
        "total_events": Event.objects.exclude(status=Event.Status.DRAFT).count(),
        "total_tickets": Booking.objects.filter(status=Booking.Status.CONFIRMED).aggregate(n=Sum("quantity"))["n"] or 0,
        "venues": Event.objects.exclude(status=Event.Status.DRAFT).values("venue").distinct().count(),
    })


def event_list(request):
    events = _visible_events()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        events = events.filter(Q(title__icontains=q) | Q(venue__icontains=q) | Q(description__icontains=q))
    if status in dict(Event.Status.choices):
        events = events.filter(status=status)
    paginator = Paginator(events.order_by("starts_at"), 6)
    return render(request, "events/event_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q, "status": status,
        "statuses": Event.Status.choices,
    })


def event_detail(request, slug):
    event = get_object_or_404(_visible_events(), slug=slug)
    tiers = event.tiers.all()
    is_organiser = request.user.is_authenticated and request.user == event.organiser
    form = BookingForm(event=event)
    return render(request, "events/event_detail.html", {
        "event": event, "tiers": tiers, "form": form, "is_organiser": is_organiser,
        "my_bookings": (Booking.objects.filter(customer=request.user, event=event, status=Booking.Status.CONFIRMED)
                        if request.user.is_authenticated else []),
    })


@login_required
@require_POST
def book(request, slug):
    event = get_object_or_404(_visible_events(), slug=slug)
    form = BookingForm(request.POST, event=event)
    if not form.is_valid():
        messages.error(request, "Pick a tier and a ticket quantity between 1 and 10.")
        return redirect(event)
    booking, error = Booking.create_booking(request.user, event, form.cleaned_data["tier"],
                                            form.cleaned_data["quantity"])
    if error:
        messages.error(request, error)
        return redirect(event)
    messages.success(request, f"Booked! Your reference is {booking.reference}.")
    return redirect(booking)


# ------------------------------------------------------------------- my tickets
@login_required
def my_bookings(request):
    bookings = (Booking.objects.filter(customer=request.user)
                .select_related("event").annotate(n_lines=Count("booking_lines")))
    return render(request, "events/my_bookings.html", {
        "bookings": bookings,
        "active": [b for b in bookings if b.is_active],
    })


@login_required
def booking_detail(request, reference):
    booking = get_object_or_404(Booking.objects.select_related("event"), reference=reference, customer=request.user)
    return render(request, "events/booking_detail.html", {"booking": booking})


@login_required
@require_POST
def booking_cancel(request, reference):
    booking = get_object_or_404(Booking.objects.select_related("event"), reference=reference, customer=request.user)
    if booking.cancel():
        messages.success(request, f"Booking {booking.reference} cancelled — your seats are back on sale.")
    else:
        messages.info(request, "That booking was already cancelled.")
    return redirect("my_bookings")


# ------------------------------------------------------------------- organiser
@login_required
def organiser_dashboard(request):
    events = request.user.events.annotate(
        n_tiers=Count("tiers", distinct=True),
        n_bookings=Count("bookings", filter=Q(bookings__status=Booking.Status.CONFIRMED), distinct=True),
        capacity=Sum("tiers__capacity"), sold=Sum("tiers__sold"),
    ).order_by("starts_at")
    return render(request, "events/dashboard.html", {
        "events": events,
        "revenue": Booking.objects.filter(event__organiser=request.user, status=Booking.Status.CONFIRMED)
                                   .aggregate(r=Sum(F("unit_price") * F("quantity")))["r"] or 0,
    })


@login_required
def event_create(request):
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.organiser = request.user
            event.status = Event.Status.DRAFT
            event.save()
            messages.success(request, "Event created — add at least one ticket tier, then put it on sale.")
            return redirect("event_manage", slug=event.slug)
    else:
        form = EventForm()
    return render(request, "events/event_form.html", {"form": form, "mode": "create"})


@login_required
def event_manage(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    tier_form = TierForm()
    if request.method == "POST":
        tier_form = TierForm(request.POST)
        if tier_form.is_valid():
            tier = tier_form.save(commit=False)
            tier.event = event
            tier.save()
            messages.success(request, f"Tier “{tier.name}” added.")
            return redirect("event_manage", slug=event.slug)
    return render(request, "events/event_manage.html", {
        "event": event, "tiers": event.tiers.all(), "tier_form": tier_form,
        "status_choices": Event.Status.choices,
    })


@login_required
@require_POST
def event_set_status(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    new_status = request.POST.get("status")
    if new_status not in dict(Event.Status.choices):
        messages.error(request, "Unknown status.")
    elif new_status == Event.Status.ON_SALE and not event.tiers.exists():
        messages.error(request, "Add at least one ticket tier before going on sale.")
    else:
        event.status = new_status
        event.save(update_fields=["status"])
        messages.success(request, f"“{event.title}” is now {event.get_status_display().lower()}.")
    return redirect("event_manage", slug=event.slug)


@login_required
def event_attendees(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    bookings = (event.bookings.filter(status=Booking.Status.CONFIRMED)
                .select_related("customer").prefetch_related("booking_lines__tier").order_by("created"))
    return render(request, "events/event_attendees.html", {
        "event": event, "bookings": bookings,
        "checked_in": sum(b.checked_in for b in bookings),
        "seats": sum(b.quantity for b in bookings),
    })


@login_required
@require_POST
def door_check_in(request, slug, reference):
    """Door scan: only the event organiser may admit, and only up to the paid quantity."""
    # Scoped to organiser AND event — a stranger gets a 404, never a leak.
    booking = get_object_or_404(
        Booking.objects.select_related("event"), reference=reference,
        event__slug=slug, event__organiser=request.user)
    if booking.status != Booking.Status.CONFIRMED:
        messages.error(request, "That booking is cancelled.")
    elif booking.checked_in >= booking.quantity:
        messages.warning(request, f"{booking.reference} has already been checked in "
                                  f"({booking.checked_in}/{booking.quantity}).")
    else:
        Booking.objects.filter(pk=booking.pk).update(checked_in=F("checked_in") + 1)
        booking.refresh_from_db()
        messages.success(request, f"✅ {booking.customer.username} admitted — "
                                  f"{booking.checked_in}/{booking.quantity} for {booking.reference}.")
    return redirect(request.POST.get("next") or "event_attendees", slug=booking.event.slug)


@login_required
def door_scan(request, slug):
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    recent = (event.bookings.filter(status=Booking.Status.CONFIRMED)
              .select_related("customer").order_by("-created")[:20])
    return render(request, "events/door_scan.html", {"event": event, "form": CheckInForm(), "recent": recent})


@login_required
@require_POST
def door_lookup(request, slug):
    """Accept a pasted reference (or the scanned text) and check the holder in."""
    event = get_object_or_404(Event, slug=slug, organiser=request.user)
    form = CheckInForm(request.POST)
    if form.is_valid():
        reference = form.cleaned_data["reference"].strip().upper()
        booking = event.bookings.filter(reference=reference).first()
        if booking is None:
            messages.error(request, f"No booking {reference} for this event.")
            return redirect("door_scan", slug=event.slug)
        return redirect("door_check_in", reference=booking.reference)
    messages.error(request, "Enter a booking reference.")
    return redirect("door_scan", slug=event.slug)


def ticket_stub(request, reference):
    """Printable stub — owner or organiser only."""
    booking = get_object_or_404(Booking.objects.select_related("event", "customer"), reference=reference)
    if not request.user.is_authenticated or (
            request.user != booking.customer and request.user != booking.event.organiser):
        return HttpResponse("Not your ticket.", status=403)
    return render(request, "events/ticket_stub.html", {"booking": booking})


@login_required
def profile(request):
    bookings = Booking.objects.filter(customer=request.user)
    return render(request, "account/profile.html", {
        "total_bookings": bookings.count(),
        "active_bookings": bookings.filter(status=Booking.Status.CONFIRMED).count(),
        "tickets_held": bookings.filter(status=Booking.Status.CONFIRMED).aggregate(n=Sum("quantity"))["n"] or 0,
    })
