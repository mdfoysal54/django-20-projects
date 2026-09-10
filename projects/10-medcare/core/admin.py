"""MedCare — Django admin registrations."""
from django.contrib import admin, messages

from .models import Appointment, Doctor, DoctorAvailability, Speciality


class DoctorAvailabilityInline(admin.TabularInline):
    model = DoctorAvailability
    extra = 1


@admin.register(Speciality)
class SpecialityAdmin(admin.ModelAdmin):
    list_display = ["emoji", "name", "slug", "doctor_count"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Doctors")
    def doctor_count(self, obj):
        return obj.doctors.count()


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ["user", "speciality", "fee", "slot_minutes", "room", "accepting_new", "upcoming"]
    list_filter = ["speciality", "accepting_new"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "bio"]
    inlines = [DoctorAvailabilityInline]

    @admin.display(description="Upcoming appts")
    def upcoming(self, obj):
        from django.utils import timezone
        return obj.appointments.filter(status="booked", starts_at__gte=timezone.now()).count()


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["reference", "starts_at", "patient", "doctor", "status", "reason"]
    list_filter = ["status", "doctor__speciality", "doctor"]
    search_fields = ["reference", "patient__username", "reason", "clinical_note"]
    date_hierarchy = "starts_at"
    readonly_fields = ["reference", "created", "cancelled_at", "ends_at"]
    actions = ["mark_completed", "mark_no_show"]

    @admin.action(description="Mark selected as completed")
    def mark_completed(self, request, queryset):
        n = queryset.update(status=Appointment.Status.COMPLETED)
        messages.success(request, f"{n} appointment(s) completed.")

    @admin.action(description="Mark selected as no-show")
    def mark_no_show(self, request, queryset):
        n = queryset.update(status=Appointment.Status.NO_SHOW)
        messages.warning(request, f"{n} appointment(s) marked no-show.")
