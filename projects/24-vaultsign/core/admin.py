from django.contrib import admin
from . import models
for m in (models.Room, models.Envelope, models.Signer, models.Event):
    admin.site.register(m)
