"""FinTrack — Django admin registrations."""
from decimal import Decimal

from django.contrib import admin, messages

from .models import Account, Budget, Category, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["icon", "name", "user", "kind", "opening_balance", "balance_display", "currency", "archived"]
    list_filter = ["kind", "currency", "archived"]
    search_fields = ["name", "user__username"]

    @admin.display(description="Balance")
    def balance_display(self, obj):
        return obj.balance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["icon", "name", "kind", "user"]
    list_filter = ["kind"]
    search_fields = ["name", "user__username"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["date", "user", "account", "kind", "amount", "category", "note"]
    list_filter = ["kind", "account", "category", "date"]
    search_fields = ["note", "user__username"]
    date_hierarchy = "date"
    list_per_page = 50
    actions = ["report_totals"]

    @admin.action(description="Report totals for selected rows")
    def report_totals(self, request, queryset):
        total = sum((obj.amount for obj in queryset), Decimal("0.00"))
        messages.info(request, f"{queryset.count()} transaction(s), net total {total}.")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["user", "category", "year", "month", "amount", "spent", "state"]
    list_filter = ["year", "month", "category"]
    search_fields = ["user__username", "category__name"]

    @admin.display(description="Spent")
    def spent(self, obj):
        return obj.spent

    @admin.display(description="State")
    def state(self, obj):
        return obj.state
