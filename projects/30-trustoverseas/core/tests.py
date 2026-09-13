"""Trust Overseas Ltd — domain tests: 190-day halt, GAMCA clock, credit lock, ledger."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    ZERO, Account, Branch, Client, Invoice, JournalLine, Leave, Medical, Passport,
    Staff, SubAgent, VisaCase, money,
)
from .services import (
    DomainError, advance_case, assert_download_ok, can_release, clock_in, clock_out,
    ensure_coa, names_match, open_case, petty_out, raise_invoice, recognize_revenue,
    record_medical, request_leave, take_receipt, trial_balance,
)


def boot():
    branch = Branch.hq()
    user = User.objects.create_user("officer", password="Str0ng!Passw0rd", first_name="Nadia")
    staff = Staff.objects.create(user=user, branch=branch, code="ST-001", role=Staff.Role.CASE,
                                 base_salary=Decimal("35000"))
    client = Client.objects.create(
        first_name="Karim", last_name="Mia", phone="01710000001", pin="123456", kyc=Client.KYC.OK,
    )
    today = timezone.localdate()
    passport = Passport.objects.create(
        client=client, number="A12345678", issue_date=today - timedelta(days=30),
        expiry_date=today + timedelta(days=800), blank_pages=8,
    )
    return branch, user, staff, client, passport


class MoneyAndNameTests(TestCase):
    def test_half_up(self):
        self.assertEqual(money("0.005"), Decimal("0.01"))
        self.assertEqual(money("2.675"), Decimal("2.68"))

    def test_names_match_allows_small_typo(self):
        self.assertTrue(names_match("Karim Mia", "Karim Mia"))
        self.assertTrue(names_match("Karim Mia", "Karim Mia"))
        self.assertFalse(names_match("Karim Mia", "Someone Else"))


class PassportGuardTests(TestCase):
    def setUp(self):
        self.branch, self.user, self.staff, self.client, self.passport = boot()

    def test_short_passport_cannot_open_a_file(self):
        self.passport.expiry_date = timezone.localdate() + timedelta(days=100)
        self.passport.save()
        with self.assertRaises(DomainError) as ctx:
            open_case(client=self.client, passport=self.passport, branch=self.branch, user=self.user)
        self.assertIn("190", str(ctx.exception))

    def test_blank_pages_required(self):
        self.passport.blank_pages = 1
        self.passport.save()
        with self.assertRaises(DomainError):
            open_case(client=self.client, passport=self.passport, branch=self.branch)

    def test_blacklist_blocks_open(self):
        self.client.kyc = Client.KYC.BAN
        self.client.save()
        with self.assertRaises(DomainError):
            open_case(client=self.client, passport=self.passport, branch=self.branch)

    def test_open_happy_path(self):
        case = open_case(client=self.client, passport=self.passport, branch=self.branch,
                         officer=self.staff, user=self.user)
        self.assertEqual(case.stage, VisaCase.Stage.SIGN)
        self.assertTrue(case.number.startswith("CAS-"))


class StageAndMedicalTests(TestCase):
    def setUp(self):
        self.branch, self.user, self.staff, self.client, self.passport = boot()
        self.case = open_case(client=self.client, passport=self.passport, branch=self.branch)

    def test_illegal_jump_rejected(self):
        with self.assertRaises(DomainError):
            advance_case(self.case, VisaCase.Stage.ISSUED)

    def test_fit_medical_expires_in_60_days(self):
        today = timezone.localdate()
        med = record_medical(self.case, result=Medical.Result.FIT, clinic="Gulf Lab", slip="W-1",
                             issued_on=today)
        self.assertEqual(med.expires_on, today + timedelta(days=60))
        self.assertTrue(med.is_live)

    def test_embassy_locked_when_certificate_under_5_days(self):
        today = timezone.localdate()
        advance_case(self.case, VisaCase.Stage.DOCS)
        advance_case(self.case, VisaCase.Stage.MED_SCHED)
        record_medical(self.case, result=Medical.Result.FIT, issued_on=today - timedelta(days=56))
        self.case.refresh_from_db()
        self.assertEqual(self.case.stage, VisaCase.Stage.MED_OK)
        self.assertFalse(self.case.medical.is_live)
        with self.assertRaises(DomainError) as ctx:
            advance_case(self.case, VisaCase.Stage.PORTAL)
        self.assertIn("5 days", str(ctx.exception))

    def test_unfit_archives_the_file(self):
        record_medical(self.case, result=Medical.Result.UNFIT)
        self.case.refresh_from_db()
        self.assertEqual(self.case.stage, VisaCase.Stage.REJ)


class LedgerTests(TestCase):
    def setUp(self):
        self.branch, self.user, self.staff, self.client, self.passport = boot()
        self.case = open_case(client=self.client, passport=self.passport, branch=self.branch)

    def test_invoice_sits_in_unearned_until_issued(self):
        inv = raise_invoice(case=self.case, amount=Decimal("50000"), user=self.user)
        ensure_coa()
        unearned = Account.objects.get(code="2010").balance
        revenue = Account.objects.get(code="4010").balance
        self.assertEqual(unearned, Decimal("50000.00"))
        self.assertEqual(revenue, ZERO)
        self.assertFalse(inv.revenue_recognized)
        recognize_revenue(inv, user=self.user)
        self.assertEqual(Account.objects.get(code="2010").balance, ZERO)
        self.assertEqual(Account.objects.get(code="4010").balance, Decimal("50000.00"))
        self.assertEqual(trial_balance(), ZERO)

    def test_receipt_cannot_exceed_balance(self):
        inv = raise_invoice(case=self.case, amount=Decimal("1000"))
        with self.assertRaises(DomainError):
            take_receipt(invoice=inv, amount=Decimal("1001"))

    def test_partial_then_full_receipt(self):
        inv = raise_invoice(case=self.case, amount=Decimal("1000"))
        take_receipt(invoice=inv, amount=Decimal("400"), method="bkash", reference="B1")
        inv.refresh_from_db()
        self.assertEqual(inv.balance_due, Decimal("600.00"))
        self.assertEqual(inv.status, Invoice.Status.PART)
        take_receipt(invoice=inv, amount=Decimal("600"), method="cash")
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.PAID)
        self.assertEqual(trial_balance(), ZERO)

    def test_unpaid_locks_pouch_and_download(self):
        inv = raise_invoice(case=self.case, amount=Decimal("80000"))
        self.assertFalse(can_release(self.case))
        with self.assertRaises(DomainError):
            assert_download_ok(self.case)
        take_receipt(invoice=inv, amount=inv.grand_total)
        self.assertTrue(can_release(self.case))

    def test_agent_credit_hard_stop(self):
        agent = SubAgent.objects.create(
            name="Rangpur Desk", contact="Hasan", phone="01719999999",
            credit_limit=Decimal("10000"),
        )
        self.case.agent = agent
        self.case.save()
        raise_invoice(case=self.case, amount=Decimal("50000"))
        agent.refresh_from_db()
        self.assertTrue(agent.is_locked)
        self.assertFalse(can_release(self.case))

    def test_petty_cash_keeps_books_balanced(self):
        raise_invoice(case=self.case, amount=Decimal("1000"))
        take_receipt(invoice=self.case.invoices.get(), amount=Decimal("1000"))
        petty_out(branch=self.branch, staff=self.staff, amount=Decimal("250"),
                  purpose="Wafid slip", expense_code="5020")
        self.assertEqual(trial_balance(), ZERO)
        self.assertTrue(JournalLine.objects.filter(narration="Wafid slip").exists())


class HrTests(TestCase):
    def setUp(self):
        self.branch, self.user, self.staff, self.client, self.passport = boot()

    def test_double_clock_in_rejected(self):
        clock_in(self.staff)
        with self.assertRaises(DomainError):
            clock_in(self.staff)

    def test_clock_out_requires_in(self):
        with self.assertRaises(DomainError):
            clock_out(self.staff)

    def test_leave_overlap_rejected(self):
        today = timezone.localdate()
        request_leave(self.staff, today, today + timedelta(days=2))
        with self.assertRaises(DomainError):
            request_leave(self.staff, today + timedelta(days=1), today + timedelta(days=4))


class ViewAndSeedTests(TestCase):
    def test_landing_is_public(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trust Overseas")

    def test_desk_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_track_with_pin(self):
        branch, user, staff, client, passport = boot()
        case = open_case(client=client, passport=passport, branch=branch)
        bad = self.client.get(reverse("track"), {"number": case.number, "pin": "000000"})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, "No file matches")
        self.assertNotContains(bad, "Karim Mia")
        good = self.client.get(reverse("track"), {"number": case.number, "pin": "123456"})
        self.assertContains(good, case.number)
        self.assertContains(good, "Karim Mia")

    def test_visa_download_locked_until_paid(self):
        branch, user, staff, client, passport = boot()
        case = open_case(client=client, passport=passport, branch=branch)
        raise_invoice(case=case, amount=Decimal("12000"))
        self.client.force_login(user)
        locked = self.client.get(reverse("visa_download", args=[case.number]))
        self.assertEqual(locked.status_code, 403)
        take_receipt(invoice=case.invoices.get(), amount=Decimal("12000"))
        opened = self.client.get(reverse("visa_download", args=[case.number]))
        self.assertEqual(opened.status_code, 200)
        self.assertIn("VISA POUCH", opened.content.decode())

    def test_seed_demo_populates_the_house(self):
        call_command("seed_demo", force=True)
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertGreaterEqual(Client.objects.count(), 3)
        self.assertGreaterEqual(VisaCase.objects.count(), 3)
        self.assertTrue(Invoice.objects.exists())
        self.assertEqual(trial_balance(), ZERO)
        self.assertTrue(SubAgent.objects.filter(is_locked=True).exists())
