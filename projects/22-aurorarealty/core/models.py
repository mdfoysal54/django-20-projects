"""AuroraRealty — listings, viewings, offers."""
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Agent(models.Model):
    name = models.CharField(max_length=80)
    licence = models.CharField(max_length=24, unique=True)
    def __str__(self):
        return self.name

class Listing(models.Model):
    class Status(models.TextChoices):
        LIVE = "live", "Live"
        HOLD = "hold", "Under offer"
        SOLD = "sold", "Sold"
        OFF = "off", "Withdrawn"
    code = models.CharField(max_length=16, unique=True, editable=False)
    title = models.CharField(max_length=140)
    suburb = models.CharField(max_length=80)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    beds = models.PositiveSmallIntegerField()
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name="listings")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.LIVE)
    def save(self, *a, **k):
        if not self.code:
            n = Listing.objects.count() + 1
            self.code = f"AR-{n:04d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("listing_detail", kwargs={"code": self.code})
    def __str__(self):
        return self.code

class Viewing(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="viewings")
    when = models.DateTimeField()
    visitor = models.CharField(max_length=80)
    class Meta:
        unique_together = ("listing", "when", "visitor")

class Offer(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WIN = "win", "Accepted"
        LOSE = "lose", "Declined"
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="offers")
    buyer = models.CharField(max_length=80)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    created = models.DateTimeField(auto_now_add=True)
