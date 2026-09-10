"""AetherHR services — clock, leave, BD payroll."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    ZERO, Applicant, Employee, LeaveBalance, LeaveRequest, Payslip, Punch, money,
)

WORKING_DAYS = Decimal("30")


class DomainError(ValueError):
    pass


@transaction.atomic
def clock_in(employee: Employee, when=None) -> Punch:
    when = when or timezone.now()
    day = timezone.localdate()
    punch, created = Punch.objects.select_for_update().get_or_create(
        employee=employee, day=day, defaults={"in_at": when},
    )
    if punch.in_at and not created:
        raise DomainError("Already clocked in today.")
    if punch.in_at is None:
        punch.in_at = when
        punch.save(update_fields=["in_at"])
    return punch


@transaction.atomic
def clock_out(employee: Employee, when=None) -> Punch:
    when = when or timezone.now()
    punch = Punch.objects.select_for_update().filter(employee=employee, day=timezone.localdate()).first()
    if punch is None or punch.in_at is None:
        raise DomainError("Clock in before you clock out.")
    if punch.out_at:
        raise DomainError("Already clocked out.")
    if when < punch.in_at:
        raise DomainError("Clock-out cannot be before clock-in.")
    punch.out_at = when
    punch.save(update_fields=["out_at"])
    return punch


def _overlap(employee, starts, ends, exclude_pk=None) -> bool:
    qs = LeaveRequest.objects.filter(employee=employee, status__in=(
        LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED,
    )).filter(Q(starts_on__lte=ends) & Q(ends_on__gte=starts))
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


@transaction.atomic
def request_leave(employee, kind, starts_on, ends_on, reason="") -> LeaveRequest:
    if ends_on < starts_on:
        raise DomainError("Leave cannot end before it starts.")
    days = (ends_on - starts_on).days + 1
    year = starts_on.year
    bal, _ = LeaveBalance.objects.get_or_create(
        employee=employee, kind=kind, year=year,
        defaults={"remaining": kind.days_per_year},
    )
    if Decimal(days) > bal.remaining:
        raise DomainError(f"Only {bal.remaining} day(s) of {kind} remain.")
    if _overlap(employee, starts_on, ends_on):
        raise DomainError("That window overlaps another leave request.")
    return LeaveRequest.objects.create(employee=employee, kind=kind, starts_on=starts_on,
                                       ends_on=ends_on, reason=reason)


@transaction.atomic
def decide_leave(req: LeaveRequest, approve: bool, user) -> LeaveRequest:
    if req.status != LeaveRequest.Status.PENDING:
        raise DomainError("This request is already decided.")
    req.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    req.decided_by = user
    req.save(update_fields=["status", "decided_by"])
    if approve:
        bal = LeaveBalance.objects.select_for_update().get(
            employee=req.employee, kind=req.kind, year=req.starts_on.year)
        bal.remaining = money(bal.remaining - Decimal(req.days))
        if bal.remaining < 0:
            raise DomainError("Balance went negative — refuse.")
        bal.save(update_fields=["remaining"])
    return req


@transaction.atomic
def run_payroll(employee: Employee, period: str, unpaid_days: int = 0) -> Payslip:
    if unpaid_days < 0:
        raise DomainError("Unpaid days cannot be negative.")
    daily = money(employee.gross / WORKING_DAYS)
    deduction = money(daily * unpaid_days)
    net = money(employee.gross - deduction)
    slip, _ = Payslip.objects.update_or_create(
        employee=employee, period=period,
        defaults={
            "basic": employee.basic, "house_rent": employee.house_rent,
            "medical": employee.medical, "conveyance": employee.conveyance,
            "gross": employee.gross, "unpaid_days": unpaid_days, "net": net,
        },
    )
    return slip


def advance_applicant(applicant: Applicant) -> Applicant:
    flow = [s for s, _ in Applicant.Stage.choices]
    try:
        nxt = flow[flow.index(applicant.stage) + 1]
    except (ValueError, IndexError):
        raise DomainError("This applicant cannot move further.")
    if nxt == Applicant.Stage.REJECT:
        raise DomainError("Reject from the reject action, not advance.")
    applicant.stage = nxt
    applicant.save(update_fields=["stage"])
    return applicant
