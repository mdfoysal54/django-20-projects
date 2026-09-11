"""VaultSign — document rooms, envelopes, signatures."""
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

class Room(models.Model):
    name = models.CharField(max_length=80, unique=True)
    def __str__(self):
        return self.name

class Envelope(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        SIGNED = "signed", "Signed"
        VOID = "void", "Void"
    number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=140)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="envelopes")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    def save(self, *a, **k):
        if not self.number:
            n = Envelope.objects.count() + 1
            self.number = f"ENV-{n:05d}"
        super().save(*a, **k)
    def get_absolute_url(self):
        return reverse("envelope_detail", kwargs={"number": self.number})
    def __str__(self):
        return self.number

class Signer(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name="signers")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    signed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = ("envelope", "email")

class Event(models.Model):
    envelope = models.ForeignKey(Envelope, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=24)
    note = models.CharField(max_length=160, blank=True)
