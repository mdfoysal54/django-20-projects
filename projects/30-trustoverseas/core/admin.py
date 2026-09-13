"""Trust Overseas Ltd — admin registrations."""
from django.contrib import admin

from .models import (
    Account, Attendance, Attestation, AuditLog, Branch, CaseDocument, Client,
    CustodyEvent, Department, Dependent, Invoice, InvoiceLine, JournalLine, Lead,
    Leave, Medical, Passport, Payroll, PettyCash, PortalSubmission, Receipt, Staff,
    SubAgent, VisaCase,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "trade_license", "is_hq")


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "role", "branch", "status")
    list_filter = ("role", "status", "branch")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("code", "first_name", "last_name", "phone", "kyc")
    search_fields = ("code", "first_name", "last_name", "phone")


@admin.register(Passport)
class PassportAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "expiry_date", "location")
    search_fields = ("number",)


@admin.register(VisaCase)
class VisaCaseAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "destination", "stage", "officer")
    list_filter = ("stage", "destination")
    search_fields = ("number",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "grand_total", "paid_amount", "status")
    list_filter = ("status",)


@admin.register(SubAgent)
class SubAgentAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "credit_limit", "is_locked")


admin.site.register(Department)
admin.site.register(Attendance)
admin.site.register(Leave)
admin.site.register(Payroll)
admin.site.register(Dependent)
admin.site.register(CustodyEvent)
admin.site.register(CaseDocument)
admin.site.register(Attestation)
admin.site.register(Medical)
admin.site.register(PortalSubmission)
admin.site.register(Lead)
admin.site.register(Account)
admin.site.register(InvoiceLine)
admin.site.register(JournalLine)
admin.site.register(Receipt)
admin.site.register(PettyCash)
admin.site.register(AuditLog)
