"""PulseGrid — sites, incidents, on-call."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Site(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self):
        return self.name

class Monitor(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="monitors")
    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=16, default="http")
    class Meta:
        unique_together = ("site", "name")
    def __str__(self):
        return f"{self.site}:{self.name}"

class Incident(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACK = "ack", "Acknowledged"
        RES = "res", "Resolved"
    number = models.CharField(max_length=20, unique=True, editable=False)
    monitor = models.ForeignKey(Monitor, on_delete=models.CASCADE, related_name="incidents")
    title = models.CharField(max_length=140)
    severity = models.CharField(max_length=8, default="sev2")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    def save(self, *a, **k):
        if not self.number:
            n = Incident.objects.count() + 1
            self.number = f"INC-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("incident_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class OnCall(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="oncall")
    name = models.CharField(max_length=80)
    def __str__(self):
        return f"{self.site} → {self.name}"
