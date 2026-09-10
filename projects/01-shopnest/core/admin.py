"""ShopNest — Django admin registrations."""
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Cart, CartItem, Category, Order, OrderItem, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["icon", "name", "product_count"]
    search_fields = ["name", "description"]

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["thumb", "name", "category", "price", "stock", "featured", "status", "created"]
    list_filter = ["status", "featured", "category"]
    search_fields = ["name", "description"]
    list_editable = ["price", "stock", "featured", "status"]
    list_per_page = 25
    readonly_fields = ["slug", "image_preview"]
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "category", "description")}),
        ("Commerce", {"fields": ("price", "stock", "featured", "status")}),
        ("Media", {"fields": ("image", "image_preview")}),
    )
    actions = ["publish", "unpublish"]

    @admin.display(description="Preview")
    def thumb(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="48" height="48" style="object-fit:cover;border-radius:8px">', obj.image.url)
        return "—"

    @admin.display(description="Image preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:180px;border-radius:10px">', obj.image.url)
        return "No image uploaded yet."

    @admin.action(description="Publish selected products")
    def publish(self, request, queryset):
        updated = queryset.update(status=Product.Status.PUBLISHED)
        messages.success(request, f"{updated} product(s) published.")

    @admin.action(description="Unpublish selected products")
    def unpublish(self, request, queryset):
        updated = queryset.update(status=Product.Status.DRAFT)
        messages.success(request, f"{updated} product(s) moved to draft.")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "user", "status", "item_total", "total_amount", "city", "created"]
    list_filter = ["status", "city", "created"]
    search_fields = ["user__username", "user__email", "phone"]
    inlines = [OrderItemInline]
    readonly_fields = ["user", "total_amount", "number", "created"]
    date_hierarchy = "created"
    actions = ["mark_paid", "mark_shipped", "mark_delivered", "cancel"]

    @admin.display(description="Items")
    def item_total(self, obj):
        return sum(i.quantity for i in obj.items.all())

    @admin.action(description="Mark selected as paid")
    def mark_paid(self, request, queryset):
        queryset.update(status=Order.Status.PAID)

    @admin.action(description="Mark selected as shipped")
    def mark_shipped(self, request, queryset):
        queryset.update(status=Order.Status.SHIPPED)

    @admin.action(description="Mark selected as delivered")
    def mark_delivered(self, request, queryset):
        queryset.update(status=Order.Status.DELIVERED)

    @admin.action(description="Cancel selected orders")
    def cancel(self, request, queryset):
        queryset.update(status=Order.Status.CANCELLED)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["user", "item_count", "total", "updated"]
    search_fields = ["user__username"]

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


admin.site.register(CartItem)
