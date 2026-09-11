"""Salonova — appointments, stylists, chairs."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Stylist(models.Model):
    name = models.CharField(max_length=80)
    specialty = models.CharField(max_length=40, default="cut")
    def __str__(self):
        return self.name

class Service(models.Model):
    name = models.CharField(max_length=80)
    minutes = models.PositiveSmallIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=24, blank=True)
    def __str__(self):
        return self.name

class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOK = "book", "Booked"
        IN = "in", "In chair"
        DONE = "done", "Done"
        CX = "cx", "Cancelled"
    number = models.CharField(max_length=20, unique=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="appointments")
    stylist = models.ForeignKey(Stylist, on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT)
    start = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.BOOK)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%Y%m%d")
            n = Appointment.objects.filter(number__startswith=f"APT-{day}").count() + 1
            self.number = f"APT-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("appointment_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number
