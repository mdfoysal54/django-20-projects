from django.contrib import admin
from . import models

for m in (models.Venue, models.DiningTable, models.Guest, models.Reservation, models.MenuItem, models.Ticket, models.TicketLine):
    admin.site.register(m)
