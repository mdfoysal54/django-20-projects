"""Seed InvoicePro with clients, invoices in every state, payments and expenses."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Client, Expense, Invoice, LineItem, Payment

CLIENTS = [
    ("Ashraf Textiles", "Ashraf Textiles Ltd", "accounts@ashraf.example", "14 Gulshan Avenue, Dhaka 1212",
     "VAT-1928374", "5.00", 14),
    ("Meridian Health", "Meridian Health Group", "ap@meridian.example", "Sector 7, Uttara, Dhaka 1230",
     "VAT-5566210", "7.50", 30),
    ("Northfield Academy", "Northfield Academy", "bursar@northfield.example", "12 Lake Road, Dhanmondi",
     "VAT-8842001", "5.00", 21),
    ("Solstice Coffee", "Solstice Coffee Roasters", "hello@solstice.example", "Banani 11, Dhaka 1213",
     "", "0.00", 7),
    ("Zenith Consulting", "Zenith Consulting FZ-LLC", "finance@zenith.example", "Business Bay, Dubai",
     "TRN-1002934", "5.00", 30),
]

INVOICES = [
    # (client index, days ago issued, items, tax, discount, target state, payments)
    (0, 46, [("Brand identity system", "1.00", "85000.00"), ("Packaging artwork", "3.00", "12000.00")],
     "5.00", "0.00", "paid", [("45000.00", "bank"), ("59000.00", "bank")]),
    (1, 38, [("Patient portal — sprint 4", "1.00", "120000.00")], "7.50", "5000.00", "overdue", []),
    (2, 21, [("Learning platform retainer", "1.00", "65000.00"), ("Teacher training workshop", "2.00", "15000.00")],
     "5.00", "0.00", "partial", [("40000.00", "mobile")]),
    (3, 9, [("Menu photography", "2.00", "8500.00")], "0.00", "0.00", "sent", []),
    (4, 5, [("Data platform audit", "1.00", "210000.00"), ("Follow-up report", "1.00", "35000.00")],
     "5.00", "10000.00", "sent", []),
    (0, 2, [("March retainer", "1.00", "55000.00")], "5.00", "0.00", "draft", []),
    (1, 1, [("Accessibility review", "1.00", "48000.00")], "7.50", "0.00", "draft", []),
    (2, 65, [("Website rebuild — phase 1", "1.00", "150000.00")], "5.00", "0.00", "paid",
     [("157500.00", "bank")]),
    (3, 75, [("Interior signage concept", "1.00", "30000.00")], "0.00", "0.00", "overdue", []),
]

EXPENSES = [
    ("Adobe Creative Cloud", "8900.00", "Software", 20),
    ("External SSD 2TB", "18500.00", "Hardware", 12),
    ("Client lunch — Ashraf Textiles", "4200.00", "Meals", 8),
    ("Uber to Meridian kickoff", "1350.00", "Travel", 6),
    ("Stripe fees (March)", "3100.00", "Fees", 3),
]


class Command(BaseCommand):
    help = "Create demo clients, invoices, payments and expenses."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        freelancer, created = User.objects.get_or_create(
            username="freelancer", defaults={"first_name": "Tanvir", "last_name": "Ahmed",
                                             "email": "hello@tanvir.studio"})
        if created:
            freelancer.set_password("DemoPass123!")
            freelancer.save()

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@invoicepro.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        for name, company, email, address, tax_id, tax_rate, terms in CLIENTS:
            Client.objects.get_or_create(owner=freelancer, name=name,
                                         defaults={"company": company, "email": email, "address": address,
                                                   "tax_id": tax_id, "default_tax_rate": Decimal(tax_rate),
                                                   "default_terms_days": terms})

        today = timezone.localdate()
        for idx, (client_idx, days_ago, items, tax, discount, state, payments) in enumerate(INVOICES):
            client = Client.objects.get(owner=freelancer, name=CLIENTS[client_idx][0])
            issue = today - timedelta(days=days_ago)
            invoice = Invoice.objects.create(
                owner=freelancer, client=client, issue_date=issue,
                due_date=issue + timedelta(days=client.default_terms_days),
                tax_rate=Decimal(tax), discount=Decimal(discount),
                notes="Payment by bank transfer. Please quote the invoice number.",
                status=Invoice.Status.DRAFT,
            )
            for order, (description, quantity, price) in enumerate(items):
                LineItem.objects.create(invoice=invoice, description=description,
                                        quantity=Decimal(quantity), unit_price=Decimal(price), order=order)

            if state != "draft":
                invoice.mark_sent()
                Invoice.objects.filter(pk=invoice.pk).update(sent_at=timezone.now() - timedelta(days=days_ago - 1))

            for amount, method in payments:
                payment, error = invoice.record_payment(Decimal(amount), method=method,
                                                        reference=f"TXN-{invoice.number[-4:]}-{idx}")
                if payment:
                    Payment.objects.filter(pk=payment.pk).update(paid_on=issue + timedelta(days=7))

            invoice.refresh_from_db()
            if state == "overdue" and invoice.balance > 0:
                Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.OVERDUE)

        for description, amount, category, days_ago in EXPENSES:
            Expense.objects.get_or_create(owner=freelancer, description=description,
                                          defaults={"amount": Decimal(amount), "category": category,
                                                    "incurred_on": today - timedelta(days=days_ago)})

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Client.objects.count()} clients, {Invoice.objects.count()} invoices, "
            f"{Payment.objects.count()} payments, {Expense.objects.count()} expenses."
        ))
