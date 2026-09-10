"""StayHub — Django admin registrations."""
from django.contrib import admin, messages

from .models import Booking, Hotel, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1
    fields = ["number", "room_type", "capacity", "price_per_night", "is_active"]


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "star_rating", "room_count", "min_price", "is_active", "owner"]
    list_filter = ["city", "star_rating", "is_active"]
    search_fields = ["name", "city", "address"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RoomInline]

    @admin.display(description="Rooms")
    def room_count(self, obj):
        return obj.room_count

    @admin.display(description="From")
    def min_price(self, obj):
        return obj.min_price


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["hotel", "number", "room_type", "capacity", "price_per_night", "is_active"]
    list_filter = ["room_type", "is_active", "hotel"]
    search_fields = ["hotel__name", "number"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["reference", "guest", "room", "check_in", "check_out", "nights", "status", "total_price"]
    list_filter = ["status", "check_in", "room__hotel"]
    search_fields = ["guest__username", "guest__email", "room__hotel__name"]
    date_hierarchy = "check_in"
    readonly_fields = ["guest", "room", "check_in", "check_out", "total_price", "created", "reference"]
    actions = ["confirm", "cancel", "complete"]

    @admin.display(description="Ref")
    def reference(self, obj):
        return obj.reference

    @admin.display(description="Nights")
    def nights(self, obj):
        return obj.nights

    @admin.action(description="Confirm selected bookings")
    def confirm(self, request, queryset):
        n = queryset.update(status=Booking.Status.CONFIRMED)
        messages.success(request, f"{n} booking(s) confirmed. Emails are sent in production.")

    @admin.action(description="Cancel selected bookings")
    def cancel(self, request, queryset):
        n = queryset.update(status=Booking.Status.CANCELLED)
        messages.success(request, f"{n} booking(s) cancelled — dates released.")

    @admin.action(description="Mark selected bookings completed")
    def complete(self, request, queryset):
        n = queryset.update(status=Booking.Status.COMPLETED)
        messages.success(request, f"{n} booking(s) marked completed.")
