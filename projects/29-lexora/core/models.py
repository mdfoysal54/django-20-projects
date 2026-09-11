"""Lexora — matters, time, retainers."""
from decimal import Decimal
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Matter(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        BILL = "bill", "Billing"
        CLOSE = "close", "Closed"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    client = models.CharField(max_length=80)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=8000)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    retainer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    def save(self, *a, **k):
        if not self.number:
            n = Matter.objects.count() + 1
            self.number = f"MAT-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("matter_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class TimeEntry(models.Model):
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, related_name="entries")
    minutes = models.PositiveIntegerField()
    note = models.CharField(max_length=200)
    billed = models.BooleanField(default=False)
    at = models.DateTimeField(auto_now_add=True)

class Invoice(models.Model):
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, related_name="invoices")
    number = models.CharField(max_length=20, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    issued = models.DateField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            n = Invoice.objects.count() + 1
            self.number = f"LEX-{n:04d}"
        super().save(*a, **k)
    def __str__(self):
        return self.number
