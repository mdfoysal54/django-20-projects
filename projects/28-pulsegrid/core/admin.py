from django.contrib import admin
from . import models
for m in (models.Site, models.Monitor, models.Incident, models.OnCall):
    admin.site.register(m)
