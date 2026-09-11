from django.contrib import admin
from . import models
for m in (models.Stylist, models.Service, models.Client, models.Appointment):
    admin.site.register(m)
