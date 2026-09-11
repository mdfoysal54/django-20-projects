"""CivicPulse — citizen issues, wards, work orders."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Ward(models.Model):
    name = models.CharField(max_length=80, unique=True)
    def __str__(self):
        return self.name

class Issue(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WORK = "work", "In works"
        DONE = "done", "Resolved"
        DUP = "dup", "Duplicate"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="issues")
    category = models.CharField(max_length=40, default="roads")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    reporter = models.CharField(max_length=80)
    def save(self, *a, **k):
        if not self.number:
            day = timezone.localdate().strftime("%y%m%d")
            n = Issue.objects.filter(number__startswith=f"CV-{day}").count() + 1
            self.number = f"CV-{day}-{n:03d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("issue_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class WorkOrder(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="orders")
    crew = models.CharField(max_length=80)
    note = models.CharField(max_length=200, blank=True)
    closed = models.BooleanField(default=False)
    opened_at = models.DateTimeField(auto_now_add=True)
