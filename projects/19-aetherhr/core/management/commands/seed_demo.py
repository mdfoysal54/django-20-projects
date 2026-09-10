"""Seed AetherHR with a small Dhaka tech company."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    Announcement, Applicant, Asset, Company, Department, Designation, Employee,
    JobPosting, LeaveBalance, LeaveType, Payslip, Profile, Punch, Review,
)
from core.services import clock_in, decide_leave, request_leave, run_payroll


class Command(BaseCommand):
    help = "Seed AetherHR demo company."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write("Refusing to seed with DEBUG=False.")
            return
        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@aetherhr.dev"})
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.first_name = "Amina"
        admin.save()
        alice, created = User.objects.get_or_create(username="alice",
                                                    defaults={"first_name": "Alice", "last_name": "Rahman",
                                                              "email": "alice@aetherhr.dev"})
        if created:
            alice.set_password("DemoPass123!")
            alice.save()
        Profile.objects.get_or_create(user=admin, defaults={"role": Profile.Role.ADMIN})
        Profile.objects.get_or_create(user=alice, defaults={"role": Profile.Role.HR})

        company = Company.get()
        company.name = "Aether Labs"
        company.save()

        eng, _ = Department.objects.get_or_create(code="eng", defaults={"name": "Engineering"})
        hr, _ = Department.objects.get_or_create(code="hr", defaults={"name": "People"})
        fin, _ = Department.objects.get_or_create(code="fin", defaults={"name": "Finance"})
        eng_role, _ = Designation.objects.get_or_create(name="Engineer", department=eng)
        lead_role, _ = Designation.objects.get_or_create(name="Lead", department=eng, defaults={"level": 3})
        hr_role, _ = Designation.objects.get_or_create(name="HRBP", department=hr)
        fin_role, _ = Designation.objects.get_or_create(name="Accountant", department=fin)

        people = [
            (admin, "E-000", hr, hr_role, "80000", "3000", "2500", None),
            (alice, "E-001", hr, hr_role, "55000", "2500", "2000", admin),
        ]
        extras = [("nadia", "Nadia", "Karim", "E-010", eng, eng_role, "40000"),
                  ("rafi", "Rafi", "Islam", "E-011", eng, lead_role, "70000"),
                  ("lina", "Lina", "Noor", "E-020", fin, fin_role, "45000")]
        employees = {}
        for user, code, dept, role, basic, med, conv, mgr_user in people:
            emp, _ = Employee.objects.get_or_create(user=user, defaults={
                "code": code, "department": dept, "designation": role,
                "basic": Decimal(basic), "medical": Decimal(med), "conveyance": Decimal(conv),
            })
            employees[user.username] = emp
        for uname, first, last, code, dept, role, basic in extras:
            u, created = User.objects.get_or_create(username=uname, defaults={"first_name": first, "last_name": last,
                                                                              "email": f"{uname}@aetherhr.dev"})
            if created:
                u.set_password("DemoPass123!")
                u.save()
            emp, _ = Employee.objects.get_or_create(user=u, defaults={
                "code": code, "department": dept, "designation": role, "basic": Decimal(basic),
                "medical": Decimal("2000"), "conveyance": Decimal("1500"),
                "manager": employees.get("admin"),
            })
            employees[uname] = emp

        annual, _ = LeaveType.objects.get_or_create(name="Annual", defaults={"days_per_year": 14})
        sick, _ = LeaveType.objects.get_or_create(name="Sick", defaults={"days_per_year": 10})
        year = timezone.localdate().year
        for emp in Employee.objects.all():
            LeaveBalance.objects.get_or_create(employee=emp, kind=annual, year=year,
                                               defaults={"remaining": 14})
            LeaveBalance.objects.get_or_create(employee=emp, kind=sick, year=year,
                                               defaults={"remaining": 10})

        nadia = employees["nadia"]
        if not nadia.leaves.exists():
            start = timezone.localdate() + timedelta(days=14)
            req = request_leave(nadia, annual, start, start + timedelta(days=2), "Family wedding")
            decide_leave(req, True, admin)

        if not Punch.objects.exists():
            try:
                clock_in(employees["alice"])
            except Exception:
                pass
        period = timezone.localdate().strftime("%Y-%m")
        if not employees["alice"].payslips.filter(period=period).exists():
            for emp in Employee.objects.filter(status=Employee.Status.ACTIVE):
                run_payroll(emp, period, unpaid_days=0)

        job, _ = JobPosting.objects.get_or_create(title="Backend engineer",
                                                  defaults={"department": eng, "body": "Django, Postgres, care."})
        Applicant.objects.get_or_create(job=job, email="hope@example.com", defaults={"name": "Hope Rahman"})
        Asset.objects.get_or_create(tag="MBP-12", defaults={"name": "MacBook Pro", "assigned_to": nadia,
                                                            "cost": Decimal("185000")})
        Announcement.objects.get_or_create(title="Eid holiday",
                                           defaults={"body": "Office closed Thursday–Saturday.", "author": admin})
        Review.objects.get_or_create(employee=nadia, period=period,
                                     defaults={"rating": 4, "goals": "Ship Nexora payroll connector.",
                                               "reviewer": alice})

        self.stdout.write(self.style.SUCCESS(
            f"AetherHR seeded: {Employee.objects.count()} people, "
            f"{Payslip.objects.count()} payslips."
        ))


