"""LinkShort — Django admin registrations."""
from django.contrib import admin, messages

from .models import Click, DailyRollup, ShortLink


class ClickInline(admin.TabularInline):
    model = Click
    extra = 0
    can_delete = False
    readonly_fields = ["created", "referrer", "device", "ip_hash", "user_agent"]
    fields = ["created", "referrer", "device", "ip_hash"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ShortLink)
class ShortLinkAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "owner", "target_short", "click_count", "status", "created", "expires_at"]
    list_filter = ["active", "created", "owner"]
    search_fields = ["code", "title", "target_url", "tags", "owner__username"]
    date_hierarchy = "created"
    readonly_fields = ["code", "click_count", "created"]
    inlines = [ClickInline]
    actions = ["enable_links", "disable_links"]

    @admin.display(description="Target")
    def target_short(self, obj):
        return obj.target_url[:60]

    @admin.display(description="Status")
    def status(self, obj):
        return obj.status_label()

    @admin.action(description="Enable selected links")
    def enable_links(self, request, queryset):
        n = queryset.update(active=True)
        messages.success(request, f"{n} link(s) enabled.")

    @admin.action(description="Disable selected links")
    def disable_links(self, request, queryset):
        n = queryset.update(active=False)
        messages.warning(request, f"{n} link(s) disabled.")


@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ["link", "created", "device", "referrer", "ip_hash_short"]
    list_filter = ["device", "created"]
    search_fields = ["link__code", "referrer", "user_agent"]
    date_hierarchy = "created"

    @admin.display(description="Visitor hash")
    def ip_hash_short(self, obj):
        return f"{obj.ip_hash[:12]}…" if obj.ip_hash else "—"


@admin.register(DailyRollup)
class DailyRollupAdmin(admin.ModelAdmin):
    list_display = ["link", "date", "clicks", "unique_visitors"]
    list_filter = ["date"]
    search_fields = ["link__code"]
