from django.contrib import admin
from . import models
for m in (models.Matter, models.TimeEntry, models.Invoice):
    admin.site.register(m)
