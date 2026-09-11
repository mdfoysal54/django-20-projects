"""Parcelio — last-mile courier OS."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Station(models.Model):
    name = models.CharField(max_length=80, unique=True)
    city = models.CharField(max_length=60)
    def __str__(self):
        return self.name

class Courier(models.Model):
    name = models.CharField(max_length=80)
    station = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="couriers")
    active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class Parcel(models.Model):
    class Status(models.TextChoices):
        CREATED = "new", "Created"
        HUB = "hub", "At hub"
        OUT = "out", "Out for delivery"
        DONE = "done", "Delivered"
        RET = "ret", "Returned"
    number = models.CharField(max_length=22, unique=True, editable=False)
    sender = models.CharField(max_length=80)
    recipient = models.CharField(max_length=80)
    dest_city = models.CharField(max_length=60)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    origin = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="outbound")
    courier = models.ForeignKey(Courier, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.CREATED)
    cod = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Parcel.objects.filter(number__startswith=f"PCL-{day}").count() + 1
            self.number = f"PCL-{day}-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("parcel_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Scan(models.Model):
    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="scans")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=16)
    note = models.CharField(max_length=120, blank=True)
