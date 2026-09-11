from django.db import transaction
from django.utils import timezone
from .models import Listing, Offer, Viewing

class DomainError(ValueError):
    pass

@transaction.atomic
def book_viewing(listing, when, visitor):
    if listing.status != Listing.Status.LIVE:
        raise DomainError("Only live listings take viewings.")
    if when < timezone.now():
        raise DomainError("Viewings cannot be in the past.")
    if Viewing.objects.filter(listing=listing, when=when).exists():
        raise DomainError("That slot is already taken.")
    return Viewing.objects.create(listing=listing, when=when, visitor=visitor)

@transaction.atomic
def place_offer(listing, buyer, amount):
    if listing.status in (Listing.Status.SOLD, Listing.Status.OFF):
        raise DomainError("This listing is closed.")
    if amount <= 0:
        raise DomainError("Offer must be positive.")
    floor = listing.price * 80 / 100
    if amount < floor:
        raise DomainError("Offers below 80% of asking are rejected.")
    offer = Offer.objects.create(listing=listing, buyer=buyer, amount=amount)
    listing.status = Listing.Status.HOLD
    listing.save(update_fields=["status"])
    return offer

@transaction.atomic
def accept_offer(offer):
    if offer.status != Offer.Status.OPEN:
        raise DomainError("Offer is not open.")
    offer.status = Offer.Status.WIN
    offer.save()
    listing = offer.listing
    listing.status = Listing.Status.SOLD
    listing.save()
    Offer.objects.filter(listing=listing, status=Offer.Status.OPEN).exclude(pk=offer.pk).update(status=Offer.Status.LOSE)
    return offer
