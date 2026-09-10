"""StayHub views — search, hotel pages, race-proof booking, guest & owner dashboards."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BookingForm, HotelFilterForm, SearchForm
from .models import Booking, Hotel, Room

DEFAULT_STAY_NIGHTS = 2


def _default_dates(request):
    """check-in/check-out from the query string, or today → today+2."""
    check_in = check_out = None
    try:
        if request.GET.get("check_in"):
            check_in = timezone.datetime.fromisoformat(request.GET["check_in"]).date()
        if request.GET.get("check_out"):
            check_out = timezone.datetime.fromisoformat(request.GET["check_out"]).date()
    except ValueError:
        check_in = check_out = None
    today = timezone.localdate()
    if not check_in or check_in < today:
        check_in = today
    if not check_out or check_out <= check_in:
        check_out = check_in + timedelta(days=DEFAULT_STAY_NIGHTS)
    return check_in, check_out


def _hotels_for(city=None, check_in=None, check_out=None, guests=None):
    hotels = Hotel.objects.filter(is_active=True)
    if city:
        hotels = hotels.filter(city__icontains=city)
    if check_in and check_out:
        hotels = hotels.exclude(
            rooms__bookings__status__in=Booking.BLOCKING_STATUSES,
            rooms__bookings__check_in__lt=check_out,
            rooms__bookings__check_out__gt=check_in,
        )
        rooms_q = Q(rooms__is_active=True)
        if guests:
            rooms_q &= Q(rooms__capacity__gte=guests)
        hotels = hotels.filter(rooms_q).distinct()
    return hotels.annotate(from_price=Min("rooms__price_per_night", filter=Q(rooms__is_active=True)))


# ------------------------------------------------------------------ public
def index(request):
    form = SearchForm(request.GET or None)
    check_in, check_out = _default_dates(request)
    hotels = _hotels_for(
        city=request.GET.get("city", "").strip() or None,
        check_in=check_in if request.GET else None,
        check_out=check_out if request.GET else None,
        guests=request.GET.get("guests"),
    )
    cities = Hotel.objects.filter(is_active=True).values_list("city", flat=True).distinct().order_by("city")
    return render(request, "stay/index.html", {
        "form": form,
        "hotels": hotels[:6],
        "cities": cities,
        "check_in": check_in,
        "check_out": check_out,
        "total_hotels": Hotel.objects.filter(is_active=True).count(),
        "total_rooms": Room.objects.filter(is_active=True).count(),
        "total_bookings": Booking.objects.exclude(status=Booking.Status.CANCELLED).count(),
    })


def search(request):
    form = SearchForm(request.GET or None)
    check_in, check_out = _default_dates(request)
    city = request.GET.get("city", "").strip()
    guests = None
    if form.is_valid():
        guests = form.cleaned_data.get("guests")
        city = form.cleaned_data.get("city") or city
    hotels = _hotels_for(city or None, check_in, check_out, guests)
    filter_form = HotelFilterForm(request.GET or None)
    if filter_form.is_valid():
        min_price = filter_form.cleaned_data.get("min_price")
        max_price = filter_form.cleaned_data.get("max_price")
        stars = filter_form.cleaned_data.get("stars")
        if min_price is not None:
            hotels = hotels.filter(from_price__gte=min_price)
        if max_price is not None:
            hotels = hotels.filter(from_price__lte=max_price)
        if stars:
            hotels = hotels.filter(star_rating__gte=int(stars))
    return render(request, "stay/search.html", {
        "form": form, "filter_form": filter_form, "hotels": hotels,
        "check_in": check_in, "check_out": check_out, "city": city,
        "nights": (check_out - check_in).days, "guests": guests,
    })


def hotel_detail(request, slug):
    hotel = get_object_or_404(Hotel, slug=slug, is_active=True)
    check_in, check_out = _default_dates(request)
    nights = (check_out - check_in).days
    rooms = hotel.rooms.filter(is_active=True).order_by("price_per_night")
    room_rows = [
        {
            "room": room,
            "available": room.is_available(check_in, check_out),
            "total": room.price_for(nights),
            "blocks": Booking.blocked_ranges(room, check_in, days=max(nights, 14)),
        }
        for room in rooms
    ]
    return render(request, "stay/hotel_detail.html", {
        "hotel": hotel, "room_rows": room_rows,
        "check_in": check_in, "check_out": check_out, "nights": nights,
        "today": timezone.localdate(),
    })


# ------------------------------------------------------------------ booking
@login_required
def booking_create(request, room_pk):
    room = get_object_or_404(Room.objects.select_related("hotel"), pk=room_pk, is_active=True)
    try:
        check_in = timezone.datetime.fromisoformat(request.GET.get("check_in", "")).date()
        check_out = timezone.datetime.fromisoformat(request.GET.get("check_out", "")).date()
    except ValueError:
        messages.error(request, "Please pick your dates first.")
        return redirect(room.hotel)
    if check_out <= check_in:
        messages.error(request, "Check-out must be after check-in.")
        return redirect(room.hotel)
    if not room.is_available(check_in, check_out):
        messages.error(request, "That room is already booked for part of those dates — try other dates.")
        return redirect(room.hotel)

    if request.method == "POST":
        form = BookingForm(request.POST, room=room, check_in=check_in, check_out=check_out)
        if form.is_valid():
            try:
                booking = Booking.create_booking(
                    guest=request.user,
                    room=room,
                    check_in=check_in,
                    check_out=check_out,
                    guests=form.cleaned_data["guests"],
                    special_requests=form.cleaned_data["special_requests"],
                )
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect(room.hotel)
            messages.success(
                request,
                f"Booking {booking.reference} created for {booking.nights} night(s) — pending confirmation.",
            )
            return redirect(booking)
    else:
        form = BookingForm(room=room, check_in=check_in, check_out=check_out)

    nights = (check_out - check_in).days
    return render(request, "stay/booking_form.html", {
        "room": room, "hotel": room.hotel, "form": form,
        "check_in": check_in, "check_out": check_out, "nights": nights,
        "total": room.price_for(nights),
    })


@login_required
def my_bookings(request):
    bookings = request.user.bookings.select_related("room", "room__hotel").all()
    return render(request, "stay/my_bookings.html", {"bookings": bookings})


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related("room", "room__hotel"), pk=pk, guest=request.user
    )
    return render(request, "stay/booking_detail.html", {"booking": booking})


@login_required
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(Booking, pk=pk, guest=request.user)
    if not booking.can_cancel:
        messages.error(request, "This booking can no longer be cancelled online.")
        return redirect(booking)
    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    messages.success(request, f"Booking {booking.reference} cancelled — the dates are free again.")
    return redirect(booking)


# ------------------------------------------------------------------ owner area
@login_required
def manage_hotels(request):
    hotels = (
        Hotel.objects.filter(owner=request.user)
        .annotate(n_rooms=Count("rooms"))
        .order_by("name")
    )
    return render(request, "stay/manage_hotels.html", {"hotels": hotels})


@login_required
def manage_rooms(request, slug):
    hotel = get_object_or_404(Hotel, slug=slug, owner=request.user)   # owner-only
    today = timezone.localdate()
    room_rows = [
        {"room": room, "bookings": room.bookings.filter(
            status__in=Booking.BLOCKING_STATUSES, check_out__gte=today
        ).select_related("guest").order_by("check_in")}
        for room in hotel.rooms.order_by("number")
    ]
    return render(request, "stay/manage_rooms.html", {"hotel": hotel, "room_rows": room_rows})


# ------------------------------------------------------------------ account
@login_required
def profile(request):
    bookings = request.user.bookings.select_related("room", "room__hotel")[:5]
    return render(request, "account/profile.html", {
        "bookings": bookings,
        "hotels_owned": Hotel.objects.filter(owner=request.user).count(),
    })

