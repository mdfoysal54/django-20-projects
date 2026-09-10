"""EventTix — Django admin registrations."""
from django.contrib import admin, messages

from .models import Booking, BookingLine, Event, TicketTier


class TicketTierInline(admin.TabularInline):
    model = TicketTier
    extra = 1
    fields = ["name", "price", "capacity", "sold", "order"]
    readonly_fields = ["sold"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["cover_emoji", "title", "organiser", "venue", "starts_at", "status", "capacity", "sold"]
    list_filter = ["status", "starts_at", "organiser"]
    search_fields = ["title", "venue"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "starts_at"
    inlines = [TicketTierInline]
    actions = ["put_on_sale", "cancel_events"]

    @admin.display(description="Capacity")
    def capacity(self, obj):
        return obj.total_capacity

    @admin.display(description="Sold")
    def sold(self, obj):
        return obj.total_sold

    @admin.action(description="Put selected events on sale")
    def put_on_sale(self, request, queryset):
        n = queryset.exclude(status=Event.Status.CANCELLED).update(status=Event.Status.ON_SALE)
        messages.success(request, f"{n} event(s) on sale.")

    @admin.action(description="Cancel selected events")
    def cancel_events(self, request, queryset):
        n = queryset.update(status=Event.Status.CANCELLED)
        messages.warning(request, f"{n} event(s) cancelled.")


@admin.register(TicketTier)
class TicketTierAdmin(admin.ModelAdmin):
    list_display = ["event", "name", "price", "capacity", "sold", "remaining"]
    list_filter = ["event"]
    search_fields = ["name", "event__title"]

    @admin.display(description="Remaining")
    def remaining(self, obj):
        return obj.remaining


class BookingLineInline(admin.TabularInline):
    model = BookingLine
    extra = 0
    readonly_fields = ["tier", "quantity", "unit_price"]
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "event", "customer", "quantity", "unit_price", "status", "checked_in", "created"]
    list_filter = ["status", "event", "created"]
    search_fields = ["reference", "customer__username", "event__title"]
    readonly_fields = ["reference", "created", "cancelled_at", "checked_in"]
    date_hierarchy = "created"
    inlines = [BookingLineInline]
    actions = ["cancel_bookings"]

    @admin.action(description="Cancel selected bookings (returns seats)")
    def cancel_bookings(self, request, queryset):
        count = 0
        for booking in queryset:
            count += 1 if booking.cancel() else 0
        messages.success(request, f"{count} booking(s) cancelled; seats returned to the pool.")
