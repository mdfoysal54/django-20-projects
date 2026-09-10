from django.contrib import admin
from . import models

for m in (models.School, models.AcademicYear, models.Klass, models.Section, models.Subject,
          models.Guardian, models.Student, models.Staff, models.FeeHead, models.Invoice,
          models.Payment, models.Attendance, models.Exam, models.Score, models.Period,
          models.Book, models.Loan, models.Route, models.Rider, models.Notice, models.SmsLog,
          models.Profile):
    admin.site.register(m)
