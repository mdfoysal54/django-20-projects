from django.contrib import admin
from . import models
for m in (models.Vehicle, models.Driver, models.Trip, models.FuelLog):
    admin.site.register(m)
