"""FinTrack views — dashboard, ledger, budgets, reports and CSV import.

Every queryset is filtered by `user=request.user` at the source; there is no
view in this app that can return another user's money data.
"""
import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (AccountForm, BudgetForm, CategoryForm, CSVImportForm,
                    TransactionForm, TransferForm)
from .models import Account, Budget, Category, Transaction

MONTH_NAMES = [date(2000, m, 1).strftime("%B") for m in range(1, 13)]


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _month_context(user, year: int, month: int):
    start, end = _month_bounds(year, month)
    txns = user.transactions.filter(date__gte=start, date__lt=end)
    income = txns.filter(amount__gt=0, kind=Transaction.Kind.INCOME).aggregate(t=Sum("amount"))["t"] or Decimal("0")
    # Transfers are internal movement — excluded from income/expense totals.
    expenses = abs(txns.filter(amount__lt=0, kind=Transaction.Kind.EXPENSE).aggregate(t=Sum("amount"))["t"] or Decimal("0"))
    net = income - expenses

    by_category = (
        txns.filter(kind=Transaction.Kind.EXPENSE, category__isnull=False)
        .values("category__name", "category__icon", "category__color")
        .annotate(total=Sum("amount"), n=Count("id"))
        .order_by("total")
    )
    spend_rows = [
        {
            "name": row["category__name"], "icon": row["category__icon"], "color": row["category__color"],
            "total": abs(row["total"]), "count": row["n"],
        }
        for row in by_category
    ]
    top = max((r["total"] for r in spend_rows), default=Decimal("0")) or Decimal("1")
    for row in spend_rows:
        row["percent"] = round(float(row["total"]) * 100 / float(top))

    budgets = (
        Budget.objects.filter(user=user, year=year, month=month)
        .select_related("category").order_by("category__name")
    )
    return {
        "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "prev": (year - 1, 12) if month == 1 else (year, month - 1),
        "next": (year + 1, 1) if month == 12 else (year, month + 1),
        "income": income, "expenses": expenses, "net": net,
        "spend_rows": spend_rows, "budgets": budgets,
        "txn_count": txns.count(),
        "recent": txns.select_related("account", "category")[:10],
    }


# ------------------------------------------------------------------ dashboard
@login_required
def index(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise ValueError
    except ValueError:
        year, month = today.year, today.month
    context = _month_context(request.user, year, month)
    accounts = request.user.accounts.filter(archived=False)
    context.update({
        "accounts": accounts,
        "total_balance": sum((a.balance for a in accounts), Decimal("0.00")),
        "over_budget": [b for b in context["budgets"] if b.state == "over"],
        "goal_progress": request.user.budgets.filter(year=year, month=month).count(),
        "has_data": request.user.transactions.exists(),
    })
    return render(request, "finance/index.html", context)


# ------------------------------------------------------------------ accounts
@login_required
def account_list(request):
    accounts = request.user.accounts.all()
    return render(request, "finance/accounts.html", {
        "accounts": accounts,
        "total": sum((a.balance for a in accounts if not a.archived), Decimal("0.00")),
    })


@login_required
def account_create(request):
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, f"Account “{account.name}” created.")
            return redirect("account_list")
    else:
        form = AccountForm()
    return render(request, "finance/account_form.html", {"form": form})


@login_required
def account_detail(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)   # owner-scoped
    txns = account.transactions.select_related("category")[:50]
    return render(request, "finance/account_detail.html", {"account": account, "transactions": txns})


# ------------------------------------------------------------------ transactions
@login_required
def transaction_list(request):
    txns = request.user.transactions.select_related("account", "category")
    account_id = request.GET.get("account")
    category_id = request.GET.get("category")
    kind = request.GET.get("kind", "")
    q = request.GET.get("q", "").strip()
    if account_id and account_id.isdigit():
        txns = txns.filter(account_id=int(account_id))
    if category_id and category_id.isdigit():
        txns = txns.filter(category_id=int(category_id))
    if kind in Transaction.Kind.values:
        txns = txns.filter(kind=kind)
    if q:
        txns = txns.filter(Q(note__icontains=q) | Q(category__name__icontains=q))
    total = txns.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return render(request, "finance/transactions.html", {
        "transactions": txns[:200],
        "total": total,
        "count": txns.count(),
        "accounts": request.user.accounts.all(),
        "categories": request.user.categories.all(),
        "selected": {"account": account_id or "", "category": category_id or "", "kind": kind, "q": q},
    })


@login_required
def transaction_create(request):
    if not request.user.accounts.exists():
        messages.info(request, "Create your first account before adding transactions.")
        return redirect("account_create")
    if request.method == "POST":
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            txn = form.save()
            messages.success(request, "Transaction recorded.")
            return redirect("transaction_list")
    else:
        form = TransactionForm(user=request.user)
    return render(request, "finance/transaction_form.html", {"form": form})


@login_required
def transaction_detail(request, pk):
    txn = get_object_or_404(Transaction.objects.select_related("account", "category"), pk=pk, user=request.user)
    return render(request, "finance/transaction_detail.html", {"transaction": txn})


@login_required
def transfer_create(request):
    if request.user.accounts.filter(archived=False).count() < 2:
        messages.info(request, "You need at least two accounts to transfer between.")
        return redirect("account_list")
    if request.method == "POST":
        form = TransferForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                Transaction.create_transfer(
                    user=request.user,
                    from_account=form.cleaned_data["from_account"],
                    to_account=form.cleaned_data["to_account"],
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data["note"],
                    date_=form.cleaned_data["date"],
                )
            except Exception as exc:  # ValidationError from the model layer
                messages.error(request, str(exc))
                return redirect("transfer_create")
            messages.success(request, "Transfer recorded (both legs linked).")
            return redirect("transaction_list")
    else:
        form = TransferForm(user=request.user)
    return render(request, "finance/transfer_form.html", {"form": form})


# ------------------------------------------------------------------ categories
@login_required
def category_list(request):
    categories = request.user.categories.annotate(n=Count("transactions"))
    return render(request, "finance/categories.html", {"categories": categories})


@login_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f"Category “{category.name}” created.")
            return redirect("category_list")
    else:
        form = CategoryForm()
    return render(request, "finance/category_form.html", {"form": form})


# ------------------------------------------------------------------ budgets
@login_required
def budget_list(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year) or today.year)
    month = int(request.GET.get("month", today.month) or today.month)
    budgets = (
        Budget.objects.filter(user=request.user, year=year, month=month)
        .select_related("category").order_by("category__name")
    )
    total_budget = sum((b.amount for b in budgets), Decimal("0"))
    total_spent = sum((b.spent for b in budgets), Decimal("0"))
    return render(request, "finance/budgets.html", {
        "budgets": budgets, "year": year, "month": month, "month_name": MONTH_NAMES[month - 1],
        "total_budget": total_budget, "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
    })


@login_required
def budget_create(request):
    if not request.user.categories.filter(kind=Category.Kind.EXPENSE).exists():
        messages.info(request, "Create at least one expense category first.")
        return redirect("category_create")
    if request.method == "POST":
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.user = request.user
            budget.save()
            messages.success(request, "Budget set.")
            return redirect(f"/budgets/?year={budget.year}&month={budget.month}")
    else:
        form = BudgetForm(user=request.user)
    return render(request, "finance/budget_form.html", {"form": form})


# ------------------------------------------------------------------ CSV import
@login_required
def csv_import(request):
    result = None
    if request.method == "POST":
        form = CSVImportForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            result = _process_csv(request, form)
            form = CSVImportForm(user=request.user)
    else:
        form = CSVImportForm(user=request.user)
    return render(request, "finance/csv_import.html", {"form": form, "result": result})


def _process_csv(request, form):
    """Parse and import rows, enforcing per-row validation with a report."""
    upload = form.cleaned_data["file"]
    account = form.cleaned_data["account"]
    max_rows = form.cleaned_data["max_rows"]
    today = timezone.localdate()

    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"error": "The file isn't valid UTF-8 text — export it again as UTF-8 CSV."}

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "date" not in [f.strip().lower() for f in reader.fieldnames]:
        return {"error": "CSV needs a header row with at least: date,amount,note"}

    fields = {f.strip().lower(): f for f in reader.fieldnames}
    category_by_name = {c.name.lower(): c for c in request.user.categories.all()}

    added, skipped = [], []
    with transaction.atomic():
        for index, row in enumerate(reader, start=2):  # row 1 = header
            if len(added) >= max_rows:
                skipped.append({"row": index, "reason": f"Stopped at the {max_rows}-row limit."})
                break
            try:
                date_str = (row.get(fields["date"]) or "").strip()
                amount_str = (row.get(fields.get("amount", "amount")) or "").strip().replace(",", "")
                note = (row.get(fields.get("note", "note")) or "").strip()[:200]
                category_name = (row.get(fields.get("category", "category")) or "").strip() if "category" in fields else ""

                if not date_str:
                    raise ValueError("missing date")
                txn_date = date.fromisoformat(date_str)
                if txn_date > today:
                    raise ValueError("date is in the future")
                amount = Decimal(amount_str)
                if amount == 0:
                    raise ValueError("zero amount")

                category = category_by_name.get(category_name.lower()) if category_name else None
                transaction_obj = Transaction(
                    user=request.user, account=account, category=category,
                    kind=Transaction.Kind.INCOME if amount > 0 else Transaction.Kind.EXPENSE,
                    amount=amount, note=note or f"Imported from {upload.name}", date=txn_date,
                )
                transaction_obj.full_clean(exclude=["user"])
                transaction_obj.save()
                added.append({"row": index, "date": str(txn_date), "amount": str(amount), "note": note})
            except (ValueError, InvalidOperation, ArithmeticError) as exc:
                skipped.append({"row": index, "reason": str(exc)})
            except Exception as exc:  # model validation errors
                reason = "; ".join(getattr(exc, "messages", [str(exc)]))
                skipped.append({"row": index, "reason": reason})

    if added:
        messages.success(request, f"Imported {len(added)} transaction(s) into “{account.name}”.")
    if skipped:
        messages.warning(request, f"{len(skipped)} row(s) skipped — see the report below.")
    return {"added": added[:50], "skipped": skipped[:50], "account": account,
            "added_count": len(added), "skipped_count": len(skipped)}


# ------------------------------------------------------------------ reports
@login_required
def reports(request):
    today = timezone.localdate()
    months = []
    cursor = date(today.year, today.month, 1)
    for _ in range(6):
        start, end = _month_bounds(cursor.year, cursor.month)
        income = request.user.transactions.filter(
            date__gte=start, date__lt=end, kind=Transaction.Kind.INCOME
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")
        expenses = abs(request.user.transactions.filter(
            date__gte=start, date__lt=end, kind=Transaction.Kind.EXPENSE
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0"))
        months.append({
            "label": cursor.strftime("%b %Y"), "income": income, "expenses": expenses,
            "net": income - expenses, "year": cursor.year, "month": cursor.month,
        })
        cursor = date(cursor.year - 1, 12, 1) if cursor.month == 1 else date(cursor.year, cursor.month - 1, 1)
    months.reverse()
    peak = max([m["expenses"] for m in months] + [Decimal("1")])

    # Category breakdown for the current month
    start, end = _month_bounds(today.year, today.month)
    breakdown = (
        request.user.transactions.filter(
            date__gte=start, date__lt=end, kind=Transaction.Kind.EXPENSE, category__isnull=False
        )
        .values("category__name", "category__icon")
        .annotate(total=Sum("amount")).order_by("total")
    )
    rows = [{"name": r["category__name"], "icon": r["category__icon"], "total": abs(r["total"])}
            for r in breakdown]
    top = max([r["total"] for r in rows] + [Decimal("1")])
    for row in rows:
        row["percent"] = round(float(row["total"]) * 100 / float(top))

    return render(request, "finance/reports.html", {
        "months": months, "peak": peak, "rows": rows,
        "month_name": MONTH_NAMES[today.month - 1], "today": today,
    })


# ------------------------------------------------------------------ account
@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "accounts": request.user.accounts.count(),
        "transactions": request.user.transactions.count(),
        "categories": request.user.categories.count(),
        "budgets": request.user.budgets.count(),
        "total_balance": sum((a.balance for a in request.user.accounts.all()), Decimal("0.00")),
    })

