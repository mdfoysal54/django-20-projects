"""OrbitPay — wallets, transfers, ledgers."""
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    handle = models.SlugField(unique=True)
    currency = models.CharField(max_length=3, default="BDT")
    def __str__(self):
        return f"@{self.handle}"
    def get_absolute_url(self):
        return reverse("account_detail", kwargs={"handle": self.handle})

class Transfer(models.Model):
    class Status(models.TextChoices):
        POSTED = "post", "Posted"
        VOID = "void", "Void"
    number = models.CharField(max_length=22, unique=True, editable=False)
    src = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="out_transfers")
    dst = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="in_transfers")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    memo = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.POSTED)
    created = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Transfer.objects.filter(number__startswith=f"PAY-{day}").count() + 1
            self.number = f"PAY-{day}-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("transfer_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Entry(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="entries")
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="entries")
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # signed
    def __str__(self):
        return f"{self.account} {self.amount}"
