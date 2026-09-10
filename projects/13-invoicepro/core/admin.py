"""InvoicePro — Django admin registrations."""
from django.contrib import admin, messages

from .models import Client, Expense, Invoice, LineItem, Payment


class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0
    fields = ["order", "description", "quantity", "unit_price"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ["created"]
    fields = ["amount", "method", "reference", "paid_on", "note", "created"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "email", "owner", "default_tax_rate", "default_terms_days", "outstanding"]
    list_filter = ["owner"]
    search_fields = ["name", "company", "email", "tax_id"]

    @admin.display(description="Outstanding")
    def outstanding(self, obj):
        return obj.outstanding


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "client", "owner", "status", "issue_date", "due_date", "total", "balance", "overdue"]
    list_filter = ["status", "issue_date", "due_date", "owner"]
    search_fields = ["number", "client__name", "notes"]
    date_hierarchy = "issue_date"
    readonly_fields = ["number", "created", "sent_at", "paid_at"]
    inlines = [LineItemInline, PaymentInline]
    actions = ["mark_paid", "mark_overdue"]

    @admin.display(boolean=True, description="Overdue?")
    def overdue(self, obj):
        return obj.is_overdue

    @admin.display(description="Total")
    def total(self, obj):
        return obj.total

    @admin.display(description="Balance")
    def balance(self, obj):
        return obj.balance

    @admin.action(description="Recalculate status for selected invoices")
    def mark_paid(self, request, queryset):
        for invoice in queryset:
            invoice.refresh_status()
        messages.success(request, f"{queryset.count()} invoice status(es) recalculated.")

    @admin.action(description="Flag overdue invoices as overdue")
    def mark_overdue(self, request, queryset):
        n = 0
        for invoice in queryset:
            if invoice.is_overdue:
                invoice.status = Invoice.Status.OVERDUE
                invoice.save(update_fields=["status"])
                n += 1
        messages.warning(request, f"{n} invoice(s) marked overdue.")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["invoice", "amount", "method", "paid_on", "reference", "recorded_by"]
    list_filter = ["method", "paid_on"]
    search_fields = ["invoice__number", "reference", "note"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["description", "owner", "amount", "category", "incurred_on"]
    list_filter = ["category", "incurred_on"]
    search_fields = ["description", "category"]
