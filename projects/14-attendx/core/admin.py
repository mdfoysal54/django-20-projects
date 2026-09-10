"""AttendX — Django admin registrations."""
from django.contrib import admin, messages

from .models import AttendanceRecord, Cohort, Enrollment, Session


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    fields = ["student", "active", "joined"]
    readonly_fields = ["joined"]


class SessionInline(admin.TabularInline):
    model = Session
    extra = 0
    fields = ["date", "topic", "status", "note"]


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "teacher", "subject", "room", "student_count", "session_count", "archived"]
    list_filter = ["archived", "subject", "teacher"]
    search_fields = ["name", "code", "subject"]
    inlines = [EnrollmentInline, SessionInline]

    @admin.display(description="Students")
    def student_count(self, obj):
        return obj.student_count

    @admin.display(description="Held sessions")
    def session_count(self, obj):
        return obj.session_count


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    fields = ["student", "status", "note", "marked_by", "marked_at"]
    readonly_fields = ["marked_at"]


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["cohort", "date", "topic", "status", "attendance_rate"]
    list_filter = ["status", "date", "cohort"]
    search_fields = ["topic", "cohort__name", "note"]
    date_hierarchy = "date"
    inlines = [AttendanceRecordInline]
    actions = ["mark_held"]

    @admin.display(description="Attendance %")
    def attendance_rate(self, obj):
        rate = obj.attendance_rate
        return f"{rate}%" if rate is not None else "—"

    @admin.action(description="Mark selected sessions as held")
    def mark_held(self, request, queryset):
        n = queryset.update(status=Session.Status.HELD)
        messages.success(request, f"{n} session(s) marked as held.")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["session", "student", "status", "marked_by", "marked_at"]
    list_filter = ["status", "session__cohort"]
    search_fields = ["student__username", "session__cohort__name", "note"]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["cohort", "student", "active", "joined"]
    list_filter = ["active", "cohort"]
    search_fields = ["student__username", "cohort__name", "cohort__code"]
