from django.contrib import admin
from . import models
for m in (models.Company, models.Department, models.Designation, models.Employee, models.Punch,
          models.LeaveType, models.LeaveBalance, models.LeaveRequest, models.Payslip,
          models.JobPosting, models.Applicant, models.Review, models.Asset, models.Announcement,
          models.Profile):
    admin.site.register(m)
