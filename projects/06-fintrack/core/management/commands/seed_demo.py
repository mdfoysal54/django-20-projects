"""Seed FinTrack with a realistic six-month financial history."""
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Account, Budget, Category, Transaction

rng = Random(7)

ACCOUNTS = [
    ("Salary Account", Account.Kind.BANK, "4200.00", "🏦"),
    ("Everyday Card", Account.Kind.CARD, "650.00", "💳"),
    ("Cash Wallet", Account.Kind.CASH, "180.00", "👛"),
    ("Emergency Savings", Account.Kind.SAVINGS, "9000.00", "🐖"),
    ("bKash Wallet", Account.Kind.MOBILE, "95.00", "📱"),
]

CATEGORIES = [
    ("Salary", Category.Kind.INCOME, "💼", "#059669"),
    ("Freelance", Category.Kind.INCOME, "🧑‍💻", "#0ea5e9"),
    ("Groceries", Category.Kind.EXPENSE, "🛒", "#f59e0b"),
    ("Rent", Category.Kind.EXPENSE, "🏠", "#7c3aed"),
    ("Transport", Category.Kind.EXPENSE, "🚌", "#06b6d4"),
    ("Dining", Category.Kind.EXPENSE, "🍜", "#dc2626"),
    ("Utilities", Category.Kind.EXPENSE, "💡", "#eab308"),
    ("Health", Category.Kind.EXPENSE, "💊", "#10b981"),
    ("Entertainment", Category.Kind.EXPENSE, "🎬", "#ec4899"),
    ("Education", Category.Kind.EXPENSE, "📚", "#6366f1"),
]

# (category, min, max, times per month)
SPEND_PATTERNS = [
    ("Groceries", 35, 120, 5),
    ("Transport", 3, 18, 12),
    ("Dining", 8, 45, 7),
    ("Utilities", 25, 70, 3),
    ("Health", 10, 90, 1),
    ("Entertainment", 6, 35, 3),
    ("Education", 15, 60, 1),
]

BUDGETS = {"Groceries": 600, "Transport": 150, "Dining": 250, "Utilities": 200, "Entertainment": 120}


class Command(BaseCommand):
    help = "Create demo accounts, categories, ~6 months of transactions, transfers and budgets."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@fintrack.dev"})
        if created:
            admin.set_password("DemoPass123!")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        user, created = User.objects.get_or_create(username="alice", defaults={"email": "alice@example.com"})
        if created:
            user.set_password("DemoPass123!")
            user.save()

        if Transaction.objects.filter(user=user).exists():
            self.stdout.write(self.style.WARNING("Demo transactions already exist — skipping."))
            return

        accounts = {}
        for name, kind, opening, icon in ACCOUNTS:
            account, _ = Account.objects.get_or_create(
                user=user, name=name,
                defaults={"kind": kind, "opening_balance": Decimal(opening), "icon": icon},
            )
            accounts[name] = account

        categories = {}
        for name, kind, icon, color in CATEGORIES:
            category, _ = Category.objects.get_or_create(
                user=user, name=name, kind=kind,
                defaults={"icon": icon, "color": color},
            )
            categories[name] = category

        today = timezone.localdate()
        first_of_month = date(today.year, today.month, 1)

        def month_start(offset):
            year, month = today.year, today.month - offset
            while month <= 0:
                month += 12
                year -= 1
            return date(year, month, 1)

        created_count = 0
        with transaction.atomic():
            for offset in range(5, -1, -1):     # oldest → newest month
                start = month_start(offset)
                year, month = start.year, start.month
                days_in_month = ((date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)) - start).days
                last_day = today.day if (offset == 0) else days_in_month

                # Salary on the 1st (capped to today for the current month)
                salary_day = min(1, last_day)
                Transaction.objects.create(
                    user=user, account=accounts["Salary Account"], category=categories["Salary"],
                    kind=Transaction.Kind.INCOME, amount=Decimal("3200.00"),
                    note=f"Monthly salary ({start.strftime('%b %Y')})", date=start.replace(day=salary_day),
                )
                # Rent on the 2nd
                rent_day = min(2, last_day)
                Transaction.objects.create(
                    user=user, account=accounts["Salary Account"], category=categories["Rent"],
                    kind=Transaction.Kind.EXPENSE, amount=Decimal("-950.00"),
                    note=f"Rent ({start.strftime('%b %Y')})", date=start.replace(day=rent_day),
                )
                # Occasional freelance income
                if rng.random() > 0.4:
                    day = min(rng.randint(8, 24), last_day)
                    Transaction.objects.create(
                        user=user, account=accounts["bKash Wallet"], category=categories["Freelance"],
                        kind=Transaction.Kind.INCOME, amount=Decimal(str(rng.randint(180, 900))),
                        note="Freelance project payment", date=start.replace(day=max(day, 1)),
                    )
                # Recurring spends
                for category_name, low, high, times in SPEND_PATTERNS:
                    for _ in range(times):
                        day = rng.randint(1, last_day)
                        amount = Decimal(str(round(rng.uniform(low, high), 2)))
                        account_name = rng.choice(["Everyday Card", "Cash Wallet", "bKash Wallet"])
                        Transaction.objects.create(
                            user=user, account=accounts[account_name], category=categories[category_name],
                            kind=Transaction.Kind.EXPENSE, amount=-amount,
                            note=f"{category_name} expense", date=start.replace(day=day),
                        )
                        created_count += 1
                # Savings transfer on the 5th
                if offset:
                    Transaction.create_transfer(
                        user=user, from_account=accounts["Salary Account"],
                        to_account=accounts["Emergency Savings"], amount=Decimal("400.00"),
                        note=f"Monthly savings ({start.strftime('%b %Y')})",
                        date_=start.replace(day=min(5, last_day)),
                    )

        # Budgets for this month and last month
        for offset, factor in [(0, Decimal("1.0")), (1, Decimal("0.95"))]:
            start = month_start(offset)
            for category_name, amount in BUDGETS.items():
                Budget.objects.get_or_create(
                    user=user, category=categories[category_name], year=start.year, month=start.month,
                    defaults={"amount": (Decimal(str(amount)) * factor).quantize(Decimal("1.00"))},
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Account.objects.count()} accounts, {Category.objects.count()} categories, "
            f"{Transaction.objects.count()} transactions, {Budget.objects.count()} budgets."
        ))
