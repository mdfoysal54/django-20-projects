from django.db import transaction
from .models import FuelLog, Trip

class DomainError(ValueError):
    pass

@transaction.atomic
def open_trip(*, vehicle, driver, origin, dest, start_km):
    if start_km < vehicle.odometer:
        raise DomainError("Start km cannot rewind the odometer.")
    if Trip.objects.filter(vehicle=vehicle, status=Trip.Status.OPEN).exists():
        raise DomainError("This vehicle is already on a trip.")
    if Trip.objects.filter(driver=driver, status=Trip.Status.OPEN).exists():
        raise DomainError("This driver is already on a trip.")
    return Trip.objects.create(vehicle=vehicle, driver=driver, origin=origin, dest=dest, start_km=start_km)

@transaction.atomic
def close_trip(trip, end_km):
    if trip.status != Trip.Status.OPEN:
        raise DomainError("Trip already closed.")
    if end_km < trip.start_km:
        raise DomainError("End km cannot be below start km.")
    trip.end_km = end_km
    trip.status = Trip.Status.CLOSE
    trip.save()
    v = trip.vehicle
    v.odometer = end_km
    v.save(update_fields=["odometer"])
    return trip

@transaction.atomic
def fuel(vehicle, litres, km):
    if litres <= 0:
        raise DomainError("Litres must be positive.")
    if km < vehicle.odometer:
        raise DomainError("Fuel km cannot rewind the odometer.")
    return FuelLog.objects.create(vehicle=vehicle, litres=litres, km=km)
