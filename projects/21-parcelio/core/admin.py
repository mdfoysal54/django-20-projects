from django.contrib import admin
from . import models
for m in (models.Station, models.Courier, models.Parcel, models.Scan):
    admin.site.register(m)
