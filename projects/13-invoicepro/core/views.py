"""InvoicePro views — clients, invoices, payments and the freelancer dashboard."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ClientForm, ExpenseForm, InvoiceForm, LineItemFormSet, PaymentForm
from .models import Client, Expense, Invoice, Payment, money


def _owned_invoices(user):
    return (Invoice.objects.filter(owner=user)
            .select_related("client")
            .annotate(n_items=Count("items", distinct=True)))


def index(request):
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, "invoice/index.html", {})


@login_required
def dashboard(request):
    invoices = _owned_invoices(request.user)
    today = timezone.localdate()
    open_invoices = invoices.filter(status__in=Invoice.OPEN_STATUSES)
    outstanding = sum((inv.balance for inv in open_invoices), Decimal("0.00"))
    overdue = [inv for inv in open_invoices if inv.is_overdue]
    paid_this_month = sum(
        (p.amount for p in Payment.objects.filter(invoice__owner=request.user,
                                                  paid_on__year=today.year, paid_on__month=today.month)),
        Decimal("0.00"))
    expenses_this_month = Expense.objects.filter(owner=request.user, incurred_on__year=today.year,
                                                  incurred_on__month=today.month).aggregate(
        total=Sum("amount"))["total"] or Decimal("0.00")
    return render(request, "invoice/dashboard.html", {
        "invoices": invoices[:8],
        "outstanding": outstanding,
        "overdue": overdue,
        "overdue_total": sum((inv.balance for inv in overdue), Decimal("0.00")),
        "paid_this_month": paid_this_month,
        "net_this_month": money(paid_this_month - expenses_this_month),
        "expenses_this_month": expenses_this_month,
        "clients": request.user.clients.count(),
        "draft_count": invoices.filter(status=Invoice.Status.DRAFT).count(),
        "payments": Payment.objects.filter(invoice__owner=request.user).select_related("invoice")[:6],
        "expense_form": ExpenseForm(),
    })


# -------------------------------------------------------------------- clients
@login_required
def client_list(request):
    clients = request.user.clients.annotate(invoice_count=Count("invoices"))
    q = request.GET.get("q", "").strip()
    if q:
        clients = clients.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(email__icontains=q))
    return render(request, "invoice/client_list.html", {"clients": clients, "q": q})


@login_required
def client_form(request, pk=None):
    client = get_object_or_404(Client, pk=pk, owner=request.user) if pk else None
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save(commit=False)
            client.owner = request.user
            if Client.objects.filter(owner=request.user, name=client.name).exclude(pk=client.pk).exists():
                messages.error(request, "You already have a client with that name.")
            else:
                client.save()
                messages.success(request, "Client saved.")
                return redirect("client_list")
    else:
        form = ClientForm(instance=client)
    return render(request, "invoice/client_form.html", {"form": form, "client": client})


# ------------------------------------------------------------------- invoices
@login_required
def invoice_list(request):
    invoices = _owned_invoices(request.user)
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if status == "overdue":
        pending = [inv.pk for inv in invoices.filter(status__in=Invoice.OPEN_STATUSES) if inv.is_overdue]
        invoices = invoices.filter(pk__in=pending)
    elif status in dict(Invoice.Status.choices):
        invoices = invoices.filter(status=status)
    if q:
        invoices = invoices.filter(Q(number__icontains=q) | Q(client__name__icontains=q)
                                   | Q(items__description__icontains=q)).distinct()
    paginator = Paginator(invoices.order_by("-issue_date", "-id"), 10)   # deterministic paging
    return render(request, "invoice/invoice_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "status": status, "q": q,
        "statuses": Invoice.Status.choices,
    })


@login_required
def invoice_detail(request, number):
    invoice = get_object_or_404(Invoice.objects.select_related("client", "owner"), number=number, owner=request.user)
    return render(request, "invoice/invoice_detail.html", {
        "invoice": invoice,
        "items": invoice.items.all(),
        "payments": invoice.payments.all(),
        "payment_form": PaymentForm(invoice=invoice),
    })


@login_required
def invoice_form(request, number=None):
    invoice = get_object_or_404(Invoice, number=number, owner=request.user) if number else None
    if invoice is not None and (invoice.status not in (Invoice.Status.DRAFT, Invoice.Status.SENT)
                               or invoice.paid_total > 0):
        messages.error(request, "An invoice with recorded payments cannot be edited — reverse the payment first.")
        return redirect(invoice)

    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice, owner=request.user)
        formset = LineItemFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.owner = request.user
            invoice.save()
            formset.instance = invoice
            formset.save()
            messages.success(request, f"Invoice {invoice.number} saved.")
            return redirect(invoice)
        messages.error(request, "Please fix the highlighted problems.")
    else:
        form = InvoiceForm(instance=invoice, owner=request.user)
        if invoice is None:
            form.initial = {"issue_date": timezone.localdate(),
                            "due_date": timezone.localdate() + timedelta(days=14)}
        formset = LineItemFormSet(instance=invoice)

    if not request.user.clients.exists():
        messages.info(request, "Add a client first — invoices need someone to bill.")
        return redirect("client_form")

    return render(request, "invoice/invoice_form.html", {
        "form": form, "formset": formset, "invoice": invoice,
    })


@login_required
@require_POST
def invoice_send(request, number):
    invoice = get_object_or_404(Invoice, number=number, owner=request.user)
    try:
        invoice.mark_sent()
        messages.success(request, f"{invoice.number} marked as sent to {invoice.client.name}.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(invoice)


@login_required
@require_POST
def invoice_void(request, number):
    invoice = get_object_or_404(Invoice, number=number, owner=request.user)
    if invoice.paid_total > 0:
        messages.error(request, "Refund the payments before voiding this invoice.")
    else:
        invoice.void()
        messages.warning(request, f"{invoice.number} voided.")
    return redirect(invoice)


@login_required
@require_POST
def invoice_delete(request, number):
    invoice = get_object_or_404(Invoice, number=number, owner=request.user)
    if invoice.status != Invoice.Status.DRAFT:
        messages.error(request, "Only drafts can be deleted — void sent invoices instead.")
        return redirect(invoice)
    invoice.delete()
    messages.success(request, "Draft deleted.")
    return redirect("invoice_list")


@login_required
@require_POST
def invoice_pay(request, number):
    invoice = get_object_or_404(Invoice, number=number, owner=request.user)
    form = PaymentForm(request.POST, invoice=invoice)
    if not form.is_valid():
        messages.error(request, "; ".join(e for errors in form.errors.values() for e in errors))
        return redirect(invoice)
    payment, error = invoice.record_payment(
        amount=form.cleaned_data["amount"], method=form.cleaned_data["method"],
        reference=form.cleaned_data["reference"], note=form.cleaned_data["note"],
    )
    if error:
        messages.error(request, error)
    else:
        Payment.objects.filter(pk=payment.pk).update(paid_on=form.cleaned_data["paid_on"])
        invoice.refresh_from_db()
        messages.success(request, f"Payment of {payment.amount} recorded — "
                                  f"{'invoice settled 🎉' if invoice.balance <= 0 else f'balance {invoice.balance}'}.")
    return redirect(invoice)


@login_required
@require_POST
def payment_delete(request, pk):
    payment = get_object_or_404(Payment, pk=pk, invoice__owner=request.user)
    invoice = payment.invoice
    amount = payment.amount
    payment.delete()
    invoice.refresh_status()
    messages.warning(request, f"Payment of {amount} reversed — status recalculated to "
                              f"{invoice.get_status_display()}.")
    return redirect(invoice)


# -------------------------------------------------------------------- reports
@login_required
def aging(request):
    """Accounts-receivable aging buckets (0–30, 31–60, 61+ days)."""
    today = timezone.localdate()
    buckets = {"current": [], "1_30": [], "31_60": [], "61_plus": []}
    for invoice in _owned_invoices(request.user).filter(status__in=Invoice.OPEN_STATUSES):
        if invoice.balance <= 0:
            continue
        days = (today - invoice.due_date).days
        if days <= 0:
            buckets["current"].append(invoice)
        elif days <= 30:
            buckets["1_30"].append(invoice)
        elif days <= 60:
            buckets["31_60"].append(invoice)
        else:
            buckets["61_plus"].append(invoice)
    totals = {key: sum((inv.balance for inv in value), Decimal("0.00")) for key, value in buckets.items()}
    return render(request, "invoice/aging.html", {
        "buckets": buckets, "totals": totals,
        "grand_total": money(sum(totals.values(), Decimal("0.00"))),
    })


@login_required
def expenses(request):
    form = ExpenseForm()
    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.owner = request.user
            expense.save()
            messages.success(request, "Expense recorded.")
            return redirect("expenses")
        messages.error(request, "Could not record that expense.")
    items = request.user.expenses.all()
    return render(request, "invoice/expenses.html", {
        "form": form, "expenses": items,
        "total": sum((e.amount for e in items), Decimal("0.00")),
        "by_category": (items.values("category").annotate(total=Sum("amount"), n=Count("id")).order_by("-total")),
    })


@login_required
def profile(request):
    invoices = request.user.invoices.all()
    return render(request, "account/profile.html", {
        "clients": request.user.clients.count(),
        "invoices": invoices.count(),
        "outstanding": sum((inv.balance for inv in invoices.filter(status__in=Invoice.OPEN_STATUSES)),
                           Decimal("0.00")),
        "paid": invoices.filter(status=Invoice.Status.PAID).count(),
    })
