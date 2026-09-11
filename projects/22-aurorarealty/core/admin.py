from django.contrib import admin
from . import models
for m in (models.Agent, models.Listing, models.Viewing, models.Offer):
    admin.site.register(m)
