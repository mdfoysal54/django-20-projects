from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from .models import Account, Entry, Transfer

class DomainError(ValueError):
    pass

def balance(account) -> Decimal:
    return account.entries.aggregate(s=Sum("amount"))["s"] or Decimal("0")

@transaction.atomic
def credit(account, amount, memo="seed"):
    if amount <= 0:
        raise DomainError("Credit must be positive.")
    t = Transfer.objects.create(src=account, dst=account, amount=amount, memo=memo)
    Entry.objects.create(account=account, transfer=t, amount=amount)
    return t

@transaction.atomic
def send(*, src, dst, amount, memo=""):
    amount = Decimal(str(amount))
    if src.pk == dst.pk:
        raise DomainError("Cannot pay yourself.")
    if amount <= 0:
        raise DomainError("Amount must be positive.")
    if balance(src) < amount:
        raise DomainError("Insufficient funds.")
    t = Transfer.objects.create(src=src, dst=dst, amount=amount, memo=memo)
    Entry.objects.create(account=src, transfer=t, amount=-amount)
    Entry.objects.create(account=dst, transfer=t, amount=amount)
    return t

@transaction.atomic
def void_transfer(t):
    if t.status == Transfer.Status.VOID:
        raise DomainError("Already void.")
    if t.src_id == t.dst_id:
        raise DomainError("Seed credits cannot be voided.")
    t.status = Transfer.Status.VOID
    t.save()
    Entry.objects.create(account=t.src, transfer=t, amount=t.amount)
    Entry.objects.create(account=t.dst, transfer=t, amount=-t.amount)
    return t
