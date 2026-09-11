from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Account, Transfer
from .services import DomainError, balance, send, void_transfer


def _wallet(user):
    acct = Account.objects.filter(user=user).first()
    if acct:
        return acct
    handle = (user.username or "wallet").lower()[:40]
    n = 0
    while Account.objects.filter(handle=handle).exists():
        n += 1
        handle = f"{(user.username or 'wallet').lower()[:36]}{n}"
    return Account.objects.create(user=user, handle=handle)

NAV = [("Money", [("dashboard", "Orbit"), ("transfer_list", "Ledger"), ("transfer_new", "Send")])]

def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    return extra

def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "app/landing.html", _ctx(request))

@login_required
def dashboard(request):
    acct = _wallet(request.user)
    return render(request, "app/dashboard.html", _ctx(request, acct=acct,
        bal=balance(acct),
        rows=Transfer.objects.select_related("src", "dst").order_by("-id")[:20]))

@login_required
def transfer_list(request):
    return render(request, "app/list.html", _ctx(request, title="Ledger",
        rows=Transfer.objects.select_related("src", "dst"), kind="pay"))

@login_required
def transfer_detail(request, number):
    t = get_object_or_404(Transfer, number=number)
    if request.method == "POST":
        try:
            void_transfer(t)
            messages.success(request, "Voided.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(t)
    return render(request, "app/detail.html", _ctx(request, t=t))

@login_required
def transfer_new(request):
    src = _wallet(request.user)
    if request.method == "POST":
        try:
            dst = get_object_or_404(Account, handle=request.POST.get("handle"))
            t = send(src=src, dst=dst, amount=request.POST.get("amount") or 0, memo=request.POST.get("memo") or "")
            return redirect(t)
        except DomainError as exc:
            messages.error(request, str(exc))
    return render(request, "app/form.html", _ctx(request, src=src, bal=balance(src)))

@login_required
def account_detail(request, handle):
    acct = get_object_or_404(Account, handle=handle)
    return render(request, "app/detail.html", _ctx(request, acct=acct, bal=balance(acct), kind="acct"))

@login_required
def profile(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get("first_name") or u.first_name
        u.email = request.POST.get("email") or u.email
        u.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "account/profile.html", _ctx(request))
