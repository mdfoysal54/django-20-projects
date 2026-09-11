from django.contrib import admin
from . import models
for m in (models.Account, models.Transfer, models.Entry):
    admin.site.register(m)
