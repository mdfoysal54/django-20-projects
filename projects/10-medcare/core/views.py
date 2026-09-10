"""MedCare views — find a doctor, book a slot, and run the clinic day."""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import can_view_appointment, doctor_for, is_doctor
from .forms import AvailabilityForm, BookingForm, ClinicalNoteForm, build_doctor_form
from .models import Appointment, Doctor, Speciality

DoctorForm = build_doctor_form()


def index(request):
    today = timezone.localdate()
    return render(request, "medcare/index.html", {
        "specialities": Speciality.objects.annotate(n=Count("doctors", filter=Q(doctors__accepting_new=True))),
        "doctors": Doctor.objects.select_related("user", "speciality").filter(accepting_new=True)[:4],
        "appointments_today": Appointment.objects.filter(starts_at__date=today, status=Appointment.Status.BOOKED).count(),
        "total_doctors": Doctor.objects.count(),
    })


def doctor_list(request):
    doctors = Doctor.objects.select_related("user", "speciality")
    speciality_slug = request.GET.get("speciality", "")
    q = request.GET.get("q", "").strip()
    if speciality_slug:
        doctors = doctors.filter(speciality__slug=speciality_slug)
    if q:
        doctors = doctors.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
                                 | Q(user__username__icontains=q) | Q(bio__icontains=q))
    paginator = Paginator(doctors, 8)
    return render(request, "medcare/doctor_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q,
        "specialities": Speciality.objects.all(),
        "speciality_slug": speciality_slug,
    })


def doctor_detail(request, pk):
    doctor = get_object_or_404(Doctor.objects.select_related("user", "speciality"), pk=pk)
    requested = request.GET.get("date")
    try:
        day = date.fromisoformat(requested) if requested else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    if day < timezone.localdate():
        messages.info(request, "You cannot book a slot in the past — showing today instead.")
        day = timezone.localdate()
    slots = doctor.free_slots(day)
    return render(request, "medcare/doctor_detail.html", {
        "doctor": doctor, "day": day, "slots": slots,
        "prev_day": day - timedelta(days=1), "next_day": day + timedelta(days=1),
        "is_this_doctor": is_doctor(request.user) and doctor_for(request.user) == doctor,
        "my_upcoming": (Appointment.objects.filter(patient=request.user, doctor=doctor,
                                                   status=Appointment.Status.BOOKED,
                                                   starts_at__gte=timezone.now())
                        if request.user.is_authenticated else []),
    })


@login_required
@require_POST
def book(request, pk):
    doctor = get_object_or_404(Doctor, pk=pk)
    if not doctor.accepting_new and not Appointment.objects.filter(patient=request.user,
                                                                  doctor=doctor).exists():
        messages.error(request, "This doctor is not accepting new patients right now.")
        return redirect(doctor)
    form = BookingForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please pick a slot and describe the reason for the visit.")
        return redirect(doctor)
    appointment, error = Appointment.book(request.user, doctor, form.cleaned_data["starts_at"],
                                          form.cleaned_data["reason"])
    if error:
        messages.error(request, error)
        return redirect(doctor)
    messages.success(request, f"Appointment {appointment.reference} confirmed for "
                              f"{timezone.localtime(appointment.starts_at):%a %b %d, %H:%M}.")
    return redirect(appointment)


@login_required
def my_appointments(request):
    appointments = (Appointment.objects.filter(patient=request.user)
                    .select_related("doctor__user", "doctor__speciality"))
    upcoming = [a for a in appointments if a.status == Appointment.Status.BOOKED and not a.is_past]
    return render(request, "medcare/my_appointments.html", {
        "upcoming": upcoming,
        "past": [a for a in appointments if a not in upcoming],
    })


@login_required
def appointment_detail(request, reference):
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor__user", "doctor__speciality", "patient"),
        reference=reference)
    if not can_view_appointment(request.user, appointment):
        # 404, never 403 — we don't confirm that somebody else's appointment exists.
        from django.http import Http404
        raise Http404("No appointment found.")
    return render(request, "medcare/appointment_detail.html", {
        "appointment": appointment,
        "is_doctor": request.user == appointment.doctor.user,
        "can_see_note": request.user == appointment.doctor.user or request.user.is_staff,
        "note_form": ClinicalNoteForm(instance=appointment) if request.user == appointment.doctor.user else None,
    })


@login_required
@require_POST
def cancel(request, reference):
    appointment = get_object_or_404(Appointment, reference=reference, patient=request.user)
    if appointment.status != Appointment.Status.BOOKED:
        messages.info(request, "That appointment is no longer cancelable.")
    elif appointment.cancel():
        messages.success(request, "Appointment cancelled — the slot is free again.")
    return redirect("my_appointments")


@login_required
@require_POST
def update_note(request, reference):
    """Doctor-only: record findings and the outcome of the visit."""
    appointment = get_object_or_404(Appointment.objects.select_related("doctor"), reference=reference)
    if request.user != appointment.doctor.user:
        from django.http import Http404
        raise Http404("No appointment found.")
    form = ClinicalNoteForm(request.POST, instance=appointment)
    if form.is_valid():
        form.save()
        messages.success(request, "Consultation note saved.")
    else:
        messages.error(request, "Could not save the note.")
    return redirect(appointment)


# ------------------------------------------------------------------- clinic day
@login_required
def schedule(request):
    doctor = doctor_for(request.user)
    if doctor is None:
        messages.error(request, "Only doctors can open the clinic schedule.")
        return redirect("home")
    day_param = request.GET.get("date")
    try:
        day = date.fromisoformat(day_param) if day_param else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    appointments = (Appointment.objects.filter(doctor=doctor, starts_at__date=day)
                    .select_related("patient").order_by("starts_at"))
    planned = [s for s in doctor._iter_slots(day)]
    slot_map = []
    by_time = {a.starts_at: a for a in appointments}
    for slot in planned:
        slot_map.append({"slot": slot, "appointment": by_time.get(slot)})
    return render(request, "medcare/schedule.html", {
        "doctor": doctor, "day": day, "slot_map": slot_map,
        "prev_day": day - timedelta(days=1), "next_day": day + timedelta(days=1),
        "stats": {
            "booked": appointments.filter(status=Appointment.Status.BOOKED).count(),
            "completed": appointments.filter(status=Appointment.Status.COMPLETED).count(),
            "no_show": appointments.filter(status=Appointment.Status.NO_SHOW).count(),
            "cancelled": appointments.filter(status=Appointment.Status.CANCELLED).count(),
        },
        "week": [(day + timedelta(days=o)) for o in range(-1, 6)],
    })


@login_required
def availability(request):
    doctor = doctor_for(request.user)
    if doctor is None:
        messages.error(request, "Only doctors can manage availability.")
        return redirect("home")
    form = AvailabilityForm()
    form.instance.doctor = doctor
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            block = get_object_or_404(doctor.availability, pk=request.POST.get("block_id"))
            block.delete()
            messages.success(request, "Availability block removed.")
            return redirect("availability")
        form = AvailabilityForm(request.POST)
        form.instance.doctor = doctor
        if form.is_valid():
            form.save()
            messages.success(request, "Availability block added.")
            return redirect("availability")
    return render(request, "medcare/availability.html", {
        "doctor": doctor, "form": form, "blocks": doctor.availability.all(),
        "doctor_form": DoctorForm(instance=doctor),
    })


@login_required
@require_POST
def update_doctor_profile(request):
    doctor = doctor_for(request.user)
    if doctor is None:
        messages.error(request, "Only doctors can edit a clinic profile.")
        return redirect("home")
    form = DoctorForm(request.POST, instance=doctor)
    if form.is_valid():
        form.save()
        messages.success(request, "Clinic profile updated.")
    else:
        messages.error(request, "Could not update the profile.")
    return redirect("availability")


def profile(request):
    if not request.user.is_authenticated:
        return redirect("login")
    appointments = Appointment.objects.filter(patient=request.user)
    doctor = doctor_for(request.user)
    return render(request, "account/profile.html", {
        "total": appointments.count(),
        "upcoming": appointments.filter(status=Appointment.Status.BOOKED, starts_at__gte=timezone.now()).count(),
        "completed": appointments.filter(status=Appointment.Status.COMPLETED).count(),
        "doctor": doctor,
    })
