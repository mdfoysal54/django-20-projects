"""DevJobs — Django admin registrations."""
from django.contrib import admin, messages

from .models import Application, Company, Job, SavedJob


class JobInline(admin.TabularInline):
    model = Job
    extra = 0
    fields = ["title", "job_type", "level", "remote", "location", "status", "deadline"]
    show_change_link = True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["logo_emoji", "name", "location", "open_jobs", "owner", "created"]
    search_fields = ["name", "location", "about"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [JobInline]

    @admin.display(description="Open jobs")
    def open_jobs(self, obj):
        return obj.open_jobs


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "level", "job_type", "remote", "status", "apps", "deadline", "created"]
    list_filter = ["status", "job_type", "level", "remote", "created"]
    search_fields = ["title", "description", "tags", "company__name"]
    prepopulated_fields = {"slug": ("title",)}
    list_per_page = 25
    date_hierarchy = "created"
    actions = ["open_jobs", "close_jobs"]

    @admin.display(description="Apps")
    def apps(self, obj):
        return obj.application_count

    @admin.action(description="Open selected jobs")
    def open_jobs(self, request, queryset):
        n = queryset.update(status=Job.Status.OPEN)
        messages.success(request, f"{n} job(s) opened.")

    @admin.action(description="Close selected jobs")
    def close_jobs(self, request, queryset):
        n = queryset.update(status=Job.Status.CLOSED)
        messages.success(request, f"{n} job(s) closed.")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["job", "applicant", "status", "has_resume", "created", "updated"]
    list_filter = ["status", "created", "job__company"]
    search_fields = ["applicant__username", "applicant__email", "job__title"]
    readonly_fields = ["job", "applicant", "cover_letter", "resume", "portfolio_url", "created", "updated"]
    date_hierarchy = "created"
    actions = ["mark_reviewing", "mark_shortlisted", "mark_rejected"]

    @admin.display(boolean=True, description="Resume")
    def has_resume(self, obj):
        return bool(obj.resume)

    @admin.action(description="Mark selected as under review")
    def mark_reviewing(self, request, queryset):
        n = queryset.update(status=Application.Status.REVIEWING)
        messages.success(request, f"{n} application(s) marked under review.")

    @admin.action(description="Shortlist selected applications")
    def mark_shortlisted(self, request, queryset):
        n = queryset.update(status=Application.Status.SHORTLISTED)
        messages.success(request, f"{n} application(s) shortlisted.")

    @admin.action(description="Reject selected applications")
    def mark_rejected(self, request, queryset):
        n = queryset.update(status=Application.Status.REJECTED)
        messages.success(request, f"{n} application(s) rejected.")


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ["user", "job", "created"]
    search_fields = ["user__username", "job__title"]
