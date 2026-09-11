"""FleetNova — vehicles, trips, fuel."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Vehicle(models.Model):
    plate = models.CharField(max_length=16, unique=True)
    kind = models.CharField(max_length=24, default="van")
    odometer = models.PositiveIntegerField(default=0)
    def __str__(self):
        return self.plate

class Driver(models.Model):
    name = models.CharField(max_length=80)
    licence = models.CharField(max_length=24, unique=True)
    def __str__(self):
        return self.name

class Trip(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSE = "close", "Closed"
    number = models.CharField(max_length=20, unique=True, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="trips")
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="trips")
    origin = models.CharField(max_length=80)
    dest = models.CharField(max_length=80)
    start_km = models.PositiveIntegerField()
    end_km = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Trip.objects.filter(number__startswith=f"TR-{day}").count() + 1
            self.number = f"TR-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("trip_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class FuelLog(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="fuel")
    litres = models.DecimalField(max_digits=8, decimal_places=2)
    km = models.PositiveIntegerField()
    at = models.DateTimeField(auto_now_add=True)
