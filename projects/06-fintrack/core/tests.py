"""FinTrack domain tests — money maths, budgets, transfers, CSV import safety."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Account, Budget, Category, Transaction


def make_account(user, name="Main", opening="1000.00", **kw):
    return Account.objects.create(user=user, name=name, opening_balance=Decimal(opening), **kw)


def make_category(user, name="Groceries", kind=Category.Kind.EXPENSE):
    return Category.objects.create(user=user, name=name, kind=kind)


def make_txn(user, account, amount, *, kind=None, category=None, date_=None, note="test"):
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if kind is None:
        kind = Transaction.Kind.INCOME if amount > 0 else Transaction.Kind.EXPENSE
    return Transaction.objects.create(
        user=user, account=account, category=category, kind=kind,
        amount=amount, note=note, date=date_ or timezone.localdate(),
    )


class BalanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("trader", password="Str0ng!Passw0rd")
        self.account = make_account(self.user, opening="1000.00")

    def test_balance_is_derived_from_transactions(self):
        self.assertEqual(self.account.balance, Decimal("1000.00"))
        make_txn(self.user, self.account, "-250.50")
        make_txn(self.user, self.account, "100.00")
        self.assertEqual(self.account.balance, Decimal("849.50"))   # 1000 - 250.50 + 100

    def test_balance_can_go_negative_and_flags(self):
        make_txn(self.user, self.account, "-1500.00")
        self.assertEqual(self.account.balance, Decimal("-500.00"))
        self.assertTrue(self.account.is_negative)

    def test_expense_sign_convention_enforced(self):
        txn = Transaction(user=self.user, account=self.account, kind=Transaction.Kind.EXPENSE,
                          amount=Decimal("10.00"))
        with self.assertRaises(ValidationError):
            txn.full_clean()   # expenses must be stored negative

    def test_income_sign_convention_enforced(self):
        txn = Transaction(user=self.user, account=self.account, kind=Transaction.Kind.INCOME,
                          amount=Decimal("-10.00"))
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_zero_and_future_rejected(self):
        zero = Transaction(user=self.user, account=self.account, kind=Transaction.Kind.EXPENSE,
                           amount=Decimal("0.00"))
        with self.assertRaises(ValidationError):
            zero.full_clean()
        future = Transaction(user=self.user, account=self.account, kind=Transaction.Kind.EXPENSE,
                             amount=Decimal("-5.00"), date=timezone.localdate() + timedelta(days=2))
        with self.assertRaises(ValidationError):
            future.full_clean()

    def test_wrong_category_kind_rejected(self):
        income_cat = make_category(self.user, "Salary", Category.Kind.INCOME)
        txn = Transaction(user=self.user, account=self.account, kind=Transaction.Kind.EXPENSE,
                          category=income_cat, amount=Decimal("-20.00"))
        with self.assertRaises(ValidationError):
            txn.full_clean()


class TransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("trader", password="Str0ng!Passw0rd")
        self.a = make_account(self.user, "Cash", opening="500.00")
        self.b = make_account(self.user, "Savings", opening="2000.00")

    def test_transfer_creates_two_linked_legs(self):
        out, inn = Transaction.create_transfer(user=self.user, from_account=self.a, to_account=self.b,
                                               amount=Decimal("150.00"))
        self.assertEqual(out.amount, Decimal("-150.00"))
        self.assertEqual(inn.amount, Decimal("150.00"))
        self.assertEqual(out.transfer_group, inn.transfer_group)
        self.assertTrue(out.transfer_group)
        self.assertEqual(self.a.balance, Decimal("350.00"))
        self.assertEqual(self.b.balance, Decimal("2150.00"))

    def test_transfer_conserves_total_money(self):
        before = self.a.balance + self.b.balance
        Transaction.create_transfer(user=self.user, from_account=self.a, to_account=self.b,
                                    amount=Decimal("75.00"))
        self.assertEqual(self.a.balance + self.b.balance, before)

    def test_transfer_validation(self):
        with self.assertRaises(ValidationError):
            Transaction.create_transfer(user=self.user, from_account=self.a, to_account=self.b,
                                        amount=Decimal("0"))
        with self.assertRaises(ValidationError):
            Transaction.create_transfer(user=self.user, from_account=self.a, to_account=self.a,
                                        amount=Decimal("10"))


class BudgetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("planner", password="Str0ng!Passw0rd")
        self.account = make_account(self.user)
        self.category = make_category(self.user, "Dining")
        self.today = timezone.localdate()
        self.budget = Budget.objects.create(
            user=self.user, category=self.category, year=self.today.year, month=self.today.month,
            amount=Decimal("300.00"),
        )

    def test_spent_and_remaining_track_transactions(self):
        make_txn(self.user, self.account, "-120.00", category=self.category)
        make_txn(self.user, self.account, "-80.00", category=self.category)
        self.assertEqual(self.budget.spent, Decimal("200.00"))
        self.assertEqual(self.budget.remaining, Decimal("100.00"))
        self.assertEqual(self.budget.usage_percent, 67)
        self.assertEqual(self.budget.state, "ok")

    def test_warning_state_at_80_percent(self):
        make_txn(self.user, self.account, "-240.00", category=self.category)
        self.assertEqual(self.budget.state, "warn")
        self.assertEqual(self.budget.state_badge, "badge-warn")

    def test_over_state_at_100_percent(self):
        make_txn(self.user, self.account, "-300.00", category=self.category)
        self.assertEqual(self.budget.state, "over")
        self.assertEqual(self.budget.remaining, Decimal("0.00"))
        self.assertEqual(self.budget.state_badge, "badge-bad")

    def test_income_never_counts_against_budget(self):
        make_txn(self.user, self.account, "500.00", kind=Transaction.Kind.INCOME)
        self.assertEqual(self.budget.spent, Decimal("0.00"))   # sign filter works

    def test_budget_for_other_month_isolated(self):
        other_month = 1 if self.today.month != 1 else 2
        make_txn(self.user, self.account, "-99.00", category=self.category,
                 date_=self.today.replace(month=other_month, day=1))
        self.assertEqual(self.budget.spent, Decimal("0.00"))

    def test_income_category_budget_rejected(self):
        income_cat = make_category(self.user, "Freelance", Category.Kind.INCOME)
        budget = Budget(user=self.user, category=income_cat, year=2026, month=1, amount=Decimal("10"))
        with self.assertRaises(ValidationError):
            budget.full_clean()


class CSVImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("importer", password="Str0ng!Passw0rd")
        self.account = make_account(self.user)
        self.category = make_category(self.user, "Groceries")
        self.client.force_login(self.user)
        self.url = reverse("csv_import")

    def upload(self, content: str, filename="txns.csv"):
        file = SimpleUploadedFile(filename, content.encode("utf-8"), content_type="text/csv")
        return self.client.post(self.url, {"file": file, "account": self.account.pk, "max_rows": 100})

    def test_happy_path_import(self):
        csv_text = (
            "date,amount,note,category\n"
            f"{timezone.localdate()},-45.50,Weekly shop,Groceries\n"
            f"{timezone.localdate()},2500.00,Salary,\n"
        )
        response = self.upload(csv_text)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Transaction.objects.count(), 2)
        expense = Transaction.objects.get(amount__lt=0)
        income = Transaction.objects.get(amount__gt=0)
        self.assertEqual(expense.amount, Decimal("-45.50"))
        self.assertEqual(expense.category, self.category)
        self.assertIsNone(income.category)
        self.assertContains(response, "Imported 2")

    def test_bad_rows_are_skipped_with_reasons(self):
        csv_text = (
            "date,amount,note\n"
            f"{timezone.localdate()},-10.00,Good row\n"
            "not-a-date,-5.00,Bad date\n"
            f"{timezone.localdate() + timedelta(days=3)},-5.00,Future date\n"
            f"{timezone.localdate()},0,Zero amount\n"
        )
        response = self.upload(csv_text)
        self.assertEqual(Transaction.objects.count(), 1)
        body = response.content.decode()
        self.assertIn("Imported 1", body)
        self.assertIn("3 row(s) skipped", body)
        self.assertIn("future", body.lower())
        self.assertIn("zero", body.lower())

    def test_missing_header_rejected(self):
        response = self.upload("foo,bar\n1,2\n")
        self.assertContains(response, "header row")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_non_csv_extension_rejected(self):
        response = self.upload("date,amount\n...", filename="payload.exe")
        self.assertContains(response, "upload a .csv")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_oversize_file_rejected(self):
        big = "date,amount\n" + ("x" * (1024 * 1024 + 10))
        response = self.upload(big)
        self.assertContains(response, "1 MB")
        self.assertEqual(Transaction.objects.count(), 0)

    def test_utf8_bom_is_tolerated(self):
        csv_text = "\ufeffdate,amount,note\n" + f"{timezone.localdate()},-3.00,Snack\n"
        response = self.upload(csv_text)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(response.status_code, 200)


class OwnershipTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.bob = User.objects.create_user("bob", password="Str0ng!Passw0rd")
        self.alice_account = make_account(self.alice, name="Alice Account")
        self.bob_account = make_account(self.bob, name="Bob Account")
        self.alice_txn = make_txn(self.alice, self.alice_account, "-20.00", note="alice private")

    def test_transaction_detail_is_owner_scoped(self):
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(reverse("transaction_detail", kwargs={"pk": self.alice_txn.pk})).status_code, 404
        )

    def test_account_detail_is_owner_scoped(self):
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(reverse("account_detail", kwargs={"pk": self.alice_account.pk})).status_code, 404
        )

    def test_transaction_list_shows_only_own_data(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("transaction_list"))
        self.assertNotContains(response, "alice private")

    def test_dashboard_totals_are_per_user(self):
        make_txn(self.alice, self.alice_account, "-100.00")
        self.client.force_login(self.bob)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "Alice Account")


class FlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("user", password="Str0ng!Passw0rd")
        self.client.force_login(self.user)

    def test_expense_saved_as_negative_from_form(self):
        account = make_account(self.user)
        category = make_category(self.user)
        response = self.client.post(reverse("transaction_create"), {
            "account": account.pk, "kind": Transaction.Kind.EXPENSE, "category": category.pk,
            "amount": "42.50", "note": "Lunch", "date": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        txn = Transaction.objects.get()
        self.assertEqual(txn.amount, Decimal("-42.50"))   # sign derived server-side

    def test_transfer_requires_two_accounts(self):
        make_account(self.user, "Only One")
        response = self.client.get(reverse("transfer_create"))
        self.assertEqual(response.status_code, 302)   # bounced to account list

    def test_transfer_flow_via_http(self):
        a = make_account(self.user, "A", opening="100")
        b = make_account(self.user, "B", opening="50")
        response = self.client.post(reverse("transfer_create"), {
            "from_account": a.pk, "to_account": b.pk, "amount": "25.00",
            "note": "move", "date": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertEqual(a.balance, Decimal("75.00"))
        self.assertEqual(b.balance, Decimal("75.00"))

    def test_negative_amount_rejected_by_form(self):
        account = make_account(self.user)
        response = self.client.post(reverse("transaction_create"), {
            "account": account.pk, "kind": Transaction.Kind.EXPENSE,
            "amount": "-10.00", "note": "sneaky", "date": timezone.localdate().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Transaction.objects.exists())


class SeederTests(TestCase):
    def test_seed_demo_populates_finances(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Account.objects.count(), 3)
        self.assertGreaterEqual(Transaction.objects.count(), 60)
        self.assertTrue(Budget.objects.exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
        # Balances must be internally consistent after seeding
        user = User.objects.get(username="alice")
        for account in user.accounts.all():
            expected = account.opening_balance + sum(
                (t.amount for t in account.transactions.all()), Decimal("0.00")
            )
            self.assertEqual(account.balance, expected)

