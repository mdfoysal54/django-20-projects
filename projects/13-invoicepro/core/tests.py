"""InvoicePro domain tests — money precision, payment state machine, ownership."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Client, Expense, Invoice, LineItem, Payment, money


def make_client(owner, name="Acme Ltd", tax_rate="5.00", terms=14):
    return Client.objects.create(owner=owner, name=name, email="billing@acme.test",
                                 default_tax_rate=Decimal(tax_rate), default_terms_days=terms)


def make_invoice(owner, client=None, items=(("Design work", "2.00", "500.00"),), tax="5.00", discount="0.00"):
    # Reuse the owner's existing client, so tests can build several invoices.
    client = client or Client.objects.filter(owner=owner).first() or make_client(owner)
    invoice = Invoice.objects.create(owner=owner, client=client,
                                     issue_date=timezone.localdate(),
                                     due_date=timezone.localdate() + timedelta(days=client.default_terms_days),
                                     tax_rate=Decimal(tax), discount=Decimal(discount))
    for order, (description, quantity, price) in enumerate(items):
        LineItem.objects.create(invoice=invoice, description=description, quantity=Decimal(quantity),
                                unit_price=Decimal(price), order=order)
    return invoice


class MoneyMathsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("freelancer", password="Str0ng!Passw0rd")

    def test_subtotal_tax_and_total(self):
        invoice = make_invoice(self.owner)                      # 2 × 500 = 1000, +5% tax
        self.assertEqual(invoice.subtotal, Decimal("1000.00"))
        self.assertEqual(invoice.tax_amount, Decimal("50.00"))
        self.assertEqual(invoice.total, Decimal("1050.00"))

    def test_rounding_is_half_up_to_two_places(self):
        invoice = make_invoice(self.owner, items=(("Consulting", "1.00", "0.335"),), tax="0.00")
        self.assertEqual(invoice.subtotal, Decimal("0.34"))     # 0.335 → 0.34, not banker's rounding
        self.assertEqual(money("0.005"), Decimal("0.01"))
        self.assertEqual(money("2.675"), Decimal("2.68"))

    def test_fractional_quantity_multiplies_correctly(self):
        invoice = make_invoice(self.owner, items=(("Hours", "7.50", "120.00"),), tax="0.00")
        self.assertEqual(invoice.subtotal, Decimal("900.00"))

    def test_discount_reduces_the_taxable_base(self):
        invoice = make_invoice(self.owner, items=(("Design", "1.00", "1000.00"),), tax="10.00", discount="100.00")
        self.assertEqual(invoice.tax_amount, Decimal("90.00"))   # 10% of (1000 − 100)
        self.assertEqual(invoice.total, Decimal("990.00"))

    def test_no_floats_anywhere(self):
        invoice = make_invoice(self.owner, items=(("Odd", "3.00", "0.10"),), tax="7.50")
        for value in (invoice.subtotal, invoice.tax_amount, invoice.total, invoice.balance):
            self.assertIsInstance(value, Decimal)

    def test_invoice_number_is_sequential_and_unique(self):
        first = make_invoice(self.owner)
        second = make_invoice(self.owner)
        self.assertNotEqual(first.number, second.number)
        self.assertTrue(first.number.startswith(f"INV-{timezone.localdate():%Y}-"))
        self.assertEqual(int(second.number.split("-")[-1]), int(first.number.split("-")[-1]) + 1)


class PaymentStateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("freelancer", password="Str0ng!Passw0rd")
        self.invoice = make_invoice(self.owner)                  # total 1050.00
        self.invoice.mark_sent()

    def test_draft_cannot_take_payments(self):
        draft = make_invoice(self.owner)
        payment, error = draft.record_payment(Decimal("100.00"))
        self.assertIsNone(payment)
        self.assertIn("Send the invoice", error)

    def test_partial_payment_sets_partial_status(self):
        payment, error = self.invoice.record_payment(Decimal("500.00"))
        self.assertIsNone(error)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIAL)
        self.assertEqual(self.invoice.balance, Decimal("550.00"))
        self.assertEqual(payment.amount, Decimal("500.00"))

    def test_full_payment_marks_paid_and_stamps_time(self):
        self.invoice.record_payment(Decimal("1050.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.balance, Decimal("0.00"))
        self.assertIsNotNone(self.invoice.paid_at)

    def test_two_partials_that_complete_the_invoice(self):
        self.invoice.record_payment(Decimal("600.00"))
        self.invoice.record_payment(Decimal("450.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.payments.count(), 2)

    def test_overpayment_is_refused(self):
        payment, error = self.invoice.record_payment(Decimal("2000.00"))
        self.assertIsNone(payment)
        self.assertIn("more than the outstanding balance", error)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_total, Decimal("0.00"))

    def test_zero_and_negative_payments_refused(self):
        for bad in (Decimal("0.00"), Decimal("-50.00")):
            payment, error = self.invoice.record_payment(bad)
            self.assertIsNone(payment)
            self.assertIn("greater than zero", error)

    def test_void_invoice_cannot_be_paid(self):
        self.invoice.void()
        payment, error = self.invoice.record_payment(Decimal("100.00"))
        self.assertIsNone(payment)
        self.assertIn("void", error)

    def test_reversing_a_payment_recalculates_status(self):
        self.invoice.record_payment(Decimal("1050.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.client.force_login(self.owner)
        self.client.post(reverse("payment_delete", kwargs={"pk": self.invoice.payments.first().pk}))
        self.invoice.refresh_from_db()
        self.assertIn(self.invoice.status, (Invoice.Status.SENT, Invoice.Status.PARTIAL))
        self.assertEqual(self.invoice.balance, Decimal("1050.00"))

    def test_overdue_is_derived_from_the_due_date(self):
        # Backdate BOTH dates — the DB enforces due_date >= issue_date.
        today = timezone.localdate()
        Invoice.objects.filter(pk=self.invoice.pk).update(issue_date=today - timedelta(days=19),
                                                          due_date=today - timedelta(days=5))
        self.invoice.refresh_from_db()
        self.assertTrue(self.invoice.is_overdue)
        self.assertEqual(self.invoice.days_overdue, 5)
        self.assertEqual(self.invoice.payment_status(), Invoice.Status.OVERDUE)

    def test_completed_payment_never_moves_to_overdue(self):
        self.invoice.record_payment(Decimal("1050.00"))
        today = timezone.localdate()
        Invoice.objects.filter(pk=self.invoice.pk).update(issue_date=today - timedelta(days=44),
                                                          due_date=today - timedelta(days=30))
        self.invoice.refresh_from_db()
        self.assertFalse(self.invoice.is_overdue)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)


class WorkflowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("freelancer", password="Str0ng!Passw0rd")
        self.client_user = User.objects.create_user("rival", password="Str0ng!Passw0rd")
        self.invoice = make_invoice(self.owner)

    def test_cannot_send_an_invoice_without_items(self):
        empty = Invoice.objects.create(owner=self.owner, client=make_client(self.owner, "Empty Co"),
                                       due_date=timezone.localdate() + timedelta(days=14))
        with self.assertRaises(ValueError):
            empty.mark_sent()

    def test_void_requires_refunded_payments(self):
        self.invoice.mark_sent()
        self.invoice.record_payment(Decimal("100.00"))
        self.client.force_login(self.owner)
        self.client.post(reverse("invoice_void", kwargs={"number": self.invoice.number}))
        self.invoice.refresh_from_db()
        self.assertNotEqual(self.invoice.status, Invoice.Status.VOID)

    def test_only_drafts_can_be_deleted(self):
        self.invoice.mark_sent()
        self.client.force_login(self.owner)
        self.client.post(reverse("invoice_delete", kwargs={"number": self.invoice.number}))
        self.assertTrue(Invoice.objects.filter(pk=self.invoice.pk).exists())

    def test_sent_invoice_is_editable_until_a_payment_lands(self):
        self.invoice.mark_sent()
        self.client.force_login(self.owner)
        url = reverse("invoice_edit", kwargs={"number": self.invoice.number})
        self.assertEqual(self.client.get(url).status_code, 200)      # still editable

        self.invoice.record_payment(Decimal("10.00"))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)                  # frozen once paid into
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_total, Decimal("10.00"))

    def test_another_freelancer_cannot_touch_the_invoice(self):
        self.invoice.mark_sent()
        self.client.force_login(self.client_user)
        for name in ("invoice_detail", "invoice_edit"):
            response = self.client.get(reverse(name, kwargs={"number": self.invoice.number}))
            self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("invoice_pay", kwargs={"number": self.invoice.number}),
                                    {"amount": "10.00", "method": "bank", "paid_on": timezone.localdate().isoformat()})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.invoice.payments.count(), 0)

    def test_due_date_before_issue_date_is_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("invoice_create"), {
            "client": self.invoice.client_id,
            "issue_date": timezone.localdate().isoformat(),
            "due_date": (timezone.localdate() - timedelta(days=3)).isoformat(),
            "tax_rate": "5.00", "discount": "0.00", "notes": "",
            "items-TOTAL_FORMS": "1", "items-INITIAL_FORMS": "0", "items-MIN_NUM_FORMS": "1", "items-MAX_NUM_FORMS": "1000",
            "items-0-description": "Work", "items-0-quantity": "1", "items-0-unit_price": "100",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be before the issue date")

    def test_client_names_are_unique_per_owner(self):
        make_client(self.owner, "Same Name")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_client(self.owner, "Same Name")
        make_client(self.client_user, "Same Name")     # a different owner may reuse the name

    def test_payment_via_view_records_and_updates_status(self):
        self.invoice.mark_sent()
        self.client.force_login(self.owner)
        self.client.post(reverse("invoice_pay", kwargs={"number": self.invoice.number}),
                         {"amount": "1050.00", "method": "bank", "reference": "TXN-1",
                          "paid_on": timezone.localdate().isoformat(), "note": "Thanks"})
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.payments.count(), 1)

    def test_aging_buckets(self):
        today = timezone.localdate()
        old = make_invoice(self.owner, client=make_client(self.owner, "Old Co"),
                           items=(("Old work", "1.00", "100.00"),))
        old.mark_sent()
        Invoice.objects.filter(pk=old.pk).update(issue_date=today - timedelta(days=60),
                                                 due_date=today - timedelta(days=45))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("aging"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old Co")
        self.assertContains(response, "31–60")


class SeederTests(TestCase):
    def test_seed_demo_populates_books(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Client.objects.count(), 4)
        self.assertGreaterEqual(Invoice.objects.count(), 8)
        self.assertTrue(Payment.objects.exists())
        self.assertTrue(Invoice.objects.filter(status=Invoice.Status.PAID).exists())
        self.assertTrue(any(inv.is_overdue for inv in Invoice.objects.filter(status=Invoice.Status.OVERDUE)))
        self.assertTrue(Expense.objects.exists())
        # The ledger must reconcile: total = sum(payments) + balance for every invoice.
        for invoice in Invoice.objects.all():
            self.assertEqual(invoice.total, invoice.paid_total + invoice.balance)
