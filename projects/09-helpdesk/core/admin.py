"""HelpDesk — Django admin registrations."""
from django.contrib import admin, messages

from .models import Department, Feedback, Ticket, TicketEvent, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ["author", "created"]
    fields = ["author", "body", "internal", "created"]


class TicketEventInline(admin.TabularInline):
    model = TicketEvent
    extra = 0
    can_delete = False
    readonly_fields = ["actor", "kind", "detail", "created"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["emoji", "name", "slug", "open_tickets", "total_tickets"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Open")
    def open_tickets(self, obj):
        return obj.tickets.exclude(status__in=["resolved", "closed"]).count()

    @admin.display(description="Total")
    def total_tickets(self, obj):
        return obj.tickets.count()


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["reference", "subject", "requester", "department", "priority", "status",
                    "assignee", "sla_due", "is_breached"]
    list_filter = ["status", "priority", "department", "assignee"]
    search_fields = ["reference", "subject", "body", "requester__username"]
    date_hierarchy = "created"
    readonly_fields = ["reference", "created", "updated", "first_response_at", "resolved_at"]
    inlines = [TicketMessageInline, TicketEventInline]
    actions = ["mark_resolved", "mark_in_progress"]

    @admin.display(boolean=True, description="SLA breached?")
    def is_breached(self, obj):
        return obj.is_breached

    @admin.action(description="Resolve selected tickets")
    def mark_resolved(self, request, queryset):
        n = 0
        for ticket in queryset:
            try:
                ticket.set_status(Ticket.Status.RESOLVED, request.user)
                n += 1
            except ValueError:
                pass
        messages.success(request, f"{n} ticket(s) resolved.")

    @admin.action(description="Move selected tickets to in progress")
    def mark_in_progress(self, request, queryset):
        n = 0
        for ticket in queryset:
            try:
                ticket.set_status(Ticket.Status.IN_PROGRESS, request.user)
                n += 1
            except ValueError:
                pass
        messages.success(request, f"{n} ticket(s) in progress.")


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "internal", "created", "short_body"]
    list_filter = ["internal", "created"]
    search_fields = ["body", "ticket__reference", "author__username"]

    @admin.display(description="Message")
    def short_body(self, obj):
        return obj.body[:70]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["ticket", "score", "comment", "created"]
    list_filter = ["score"]
