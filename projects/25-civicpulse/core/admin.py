from django.contrib import admin
from . import models
for m in (models.Ward, models.Issue, models.WorkOrder):
    admin.site.register(m)
