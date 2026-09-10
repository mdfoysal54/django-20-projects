"""AetherHR domain tests — clock, leave, BD payroll."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Department, Designation, Employee, LeaveBalance, LeaveType, Payslip, money,
)
from .services import DomainError, clock_in, clock_out, decide_leave, request_leave, run_payroll


def org():
    dept = Department.objects.create(name="Engineering", code="eng")
    role = Designation.objects.create(name="Engineer", department=dept)
    user = User.objects.create_user("ada", password="Str0ng!Passw0rd", first_name="Ada")
    mgr = User.objects.create_user("hr", password="Str0ng!Passw0rd")
    emp = Employee.objects.create(user=user, code="E-1", department=dept, designation=role,
                                  basic=Decimal("40000"), medical=Decimal("2000"), conveyance=Decimal("1500"))
    hr = Employee.objects.create(user=mgr, code="E-0", department=dept, designation=role,
                                 basic=Decimal("60000"))
    kind = LeaveType.objects.create(name="Annual", days_per_year=14)
    LeaveBalance.objects.create(employee=emp, kind=kind, year=date.today().year, remaining=Decimal("14"))
    return emp, hr, kind


class PayrollTests(TestCase):
    def test_house_rent_is_half_basic_and_net_deducts_unpaid(self):
        emp, hr, kind = org()
        self.assertEqual(emp.house_rent, Decimal("20000.00"))
        self.assertEqual(emp.gross, Decimal("63500.00"))  # 40k + 20k + 2k + 1.5k
        slip = run_payroll(emp, "2026-01", unpaid_days=0)
        self.assertEqual(slip.net, emp.gross)
        slip2 = run_payroll(emp, "2026-02", unpaid_days=3)
        daily = money(emp.gross / Decimal("30"))
        self.assertEqual(slip2.net, money(emp.gross - daily * 3))


class LeaveAndClockTests(TestCase):
    def setUp(self):
        self.emp, self.hr, self.kind = org()

    def test_leave_cannot_exceed_balance_or_overlap(self):
        start = date.today() + timedelta(days=7)
        req = request_leave(self.emp, self.kind, start, start + timedelta(days=4))
        self.assertEqual(req.days, 5)
        with self.assertRaises(DomainError):
            request_leave(self.emp, self.kind, start + timedelta(days=2), start + timedelta(days=8))
        with self.assertRaises(DomainError):
            request_leave(self.emp, self.kind, start + timedelta(days=20), start + timedelta(days=40))  # 21 days > 14

    def test_approve_deducts_balance(self):
        start = date.today() + timedelta(days=10)
        req = request_leave(self.emp, self.kind, start, start + timedelta(days=2))
        decide_leave(req, True, self.hr.user)
        bal = LeaveBalance.objects.get(employee=self.emp, kind=self.kind)
        self.assertEqual(bal.remaining, Decimal("11.00"))

    def test_clock_in_out_and_double_in_refused(self):
        punch = clock_in(self.emp)
        self.assertIsNotNone(punch.in_at)
        with self.assertRaises(DomainError):
            clock_in(self.emp)
        out = clock_out(self.emp, when=timezone.now() + timedelta(hours=8))
        self.assertGreater(out.hours, Decimal("0"))


class ViewSeederTests(TestCase):
    def test_landing_public(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_clock_requires_login(self):
        self.assertEqual(self.client.get(reverse("clock")).status_code, 302)

    def test_seed_demo(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Employee.objects.count(), 4)
        self.assertTrue(Payslip.objects.exists())
        self.assertTrue(User.objects.filter(username="alice").exists())
