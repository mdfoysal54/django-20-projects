"""Trust Overseas Ltd — domain rules.

Guards that keep a visa file honest:
- Passport remaining life < 190 days blocks case opening.
- GAMCA/Wafid FIT certificates expire in 60 days; embassy submit locked under 5 days.
- Sub-agent credit hard-stop hides downloads and pouch barcodes.
- Unpaid invoice balance locks visa PDF / pouch release.
- Every money movement is a balanced journal pair (debit = credit).
- Advances sit in unearned retainers (2010) until the visa is issued.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    MEDICAL_VALID_DAYS, PASSPORT_MIN_DAYS, ZERO, Account, Attendance, AuditLog,
    Invoice, InvoiceLine, JournalLine, Leave, Medical, Passport, Payroll, PettyCash,
    Receipt, Staff, SubAgent, VisaCase, money,
)


class DomainError(ValueError):
    pass


COA = {
    "1010": ("Branch petty cash", Account.Kind.ASSET),
    "1020": ("Operating bank", Account.Kind.ASSET),
    "1030": ("Client receivables", Account.Kind.ASSET),
    "1040": ("Sub-agent receivables", Account.Kind.ASSET),
    "1050": ("Consular advances", Account.Kind.ASSET),
    "2010": ("Unearned retainers", Account.Kind.LIAB),
    "2020": ("Sub-agent payables", Account.Kind.LIAB),
    "2030": ("Accrued payroll", Account.Kind.LIAB),
    "2040": ("VAT / tax payable", Account.Kind.LIAB),
    "4010": ("Work visa fees", Account.Kind.REV),
    "4020": ("Attestation fees", Account.Kind.REV),
    "4030": ("Ticketing commission", Account.Kind.REV),
    "5010": ("Embassy / consular fees", Account.Kind.DCOST),
    "5020": ("Wafid / medical costs", Account.Kind.DCOST),
    "5030": ("Courier & apostille", Account.Kind.DCOST),
    "6010": ("Staff salaries", Account.Kind.OPEX),
    "6020": ("Rent & utilities", Account.Kind.OPEX),
}


def ensure_coa() -> None:
    for code, (name, kind) in COA.items():
        Account.objects.get_or_create(code=code, defaults={"name": name, "kind": kind})


def acct(code: str) -> Account:
    ensure_coa()
    return Account.objects.get(code=code)


def log(user, verb, obj=None, detail=""):
    AuditLog.objects.create(
        user=user, verb=verb,
        model=obj.__class__.__name__ if obj else "",
        object_id=str(getattr(obj, "pk", "") or ""),
        detail=detail[:240],
    )


def _levenshtein(a: str, b: str) -> int:
    a, b = (a or "").lower(), (b or "").lower()
    if a == b:
        return 0
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def names_match(passport_name: str, document_name: str, max_distance: int = 2) -> bool:
    return _levenshtein(passport_name, document_name) <= max_distance


# ------------------------------------------------------------------ cases
def assert_passport_ok(passport: Passport) -> None:
    if passport.needs_renewal:
        raise DomainError(
            f"Passport {passport.number} has {passport.days_left} days left "
            f"(minimum {PASSPORT_MIN_DAYS}). Renew before opening a file."
        )
    if passport.blank_pages < 2:
        raise DomainError("Passport needs at least two blank pages.")


@transaction.atomic
def open_case(*, client, passport, branch, destination="SAU", visa_category="Work",
              job_title="", agent=None, officer=None, user=None) -> VisaCase:
    if client.kyc == client.KYC.BAN:
        raise DomainError("Blacklisted clients cannot open a file.")
    assert_passport_ok(passport)
    if passport.client_id != client.pk:
        raise DomainError("Passport does not belong to this client.")
    if agent and agent.is_locked:
        raise DomainError("This sub-agent is credit-locked. Clear the ledger first.")
    case = VisaCase.objects.create(
        client=client, passport=passport, branch=branch, destination=destination,
        visa_category=visa_category, job_title=job_title, agent=agent, officer=officer,
        stage=VisaCase.Stage.SIGN,
        sla_date=timezone.localdate() + timedelta(days=45),
    )
    log(user, "open_case", case, case.number)
    return case


LEGAL = {
    VisaCase.Stage.INQ: {VisaCase.Stage.SIGN, VisaCase.Stage.REJ},
    VisaCase.Stage.SIGN: {VisaCase.Stage.DOCS, VisaCase.Stage.REJ},
    VisaCase.Stage.DOCS: {VisaCase.Stage.ATTEST, VisaCase.Stage.MED_SCHED, VisaCase.Stage.REJ},
    VisaCase.Stage.ATTEST: {VisaCase.Stage.MED_SCHED, VisaCase.Stage.MED_OK, VisaCase.Stage.REJ},
    VisaCase.Stage.MED_SCHED: {VisaCase.Stage.MED_OK, VisaCase.Stage.REJ},
    VisaCase.Stage.MED_OK: {VisaCase.Stage.PORTAL, VisaCase.Stage.EMBASSY, VisaCase.Stage.REJ},
    VisaCase.Stage.PORTAL: {VisaCase.Stage.EMBASSY, VisaCase.Stage.ISSUED, VisaCase.Stage.REJ},
    VisaCase.Stage.EMBASSY: {VisaCase.Stage.ISSUED, VisaCase.Stage.REJ},
    VisaCase.Stage.ISSUED: {VisaCase.Stage.FLIGHT},
    VisaCase.Stage.FLIGHT: {VisaCase.Stage.ARRIVED},
    VisaCase.Stage.ARRIVED: {VisaCase.Stage.POST, VisaCase.Stage.DONE},
    VisaCase.Stage.POST: {VisaCase.Stage.DONE},
}


@transaction.atomic
def advance_case(case: VisaCase, to_stage: str, user=None) -> VisaCase:
    allowed = LEGAL.get(case.stage, set())
    if to_stage not in allowed:
        raise DomainError(f"Cannot move {case.get_stage_display()} → {to_stage}.")
    if to_stage in (VisaCase.Stage.PORTAL, VisaCase.Stage.EMBASSY):
        med = getattr(case, "medical", None)
        if med is None or med.result != Medical.Result.FIT:
            raise DomainError("Embassy / portal submit needs a FIT medical.")
        if not med.is_live:
            raise DomainError(
                "GAMCA/Wafid certificate has under 5 days left (or has lapsed). "
                "Re-test before consulate submission."
            )
    if to_stage == VisaCase.Stage.ISSUED:
        for inv in case.invoices.all():
            if not inv.revenue_recognized:
                recognize_revenue(inv, user=user)
    if to_stage == VisaCase.Stage.DONE:
        case.closed_on = timezone.localdate()
    case.stage = to_stage
    case.save()
    log(user, "advance", case, to_stage)
    return case


@transaction.atomic
def record_medical(case: VisaCase, *, result: str, clinic="", slip="", issued_on=None) -> Medical:
    issued_on = issued_on or timezone.localdate()
    expires = issued_on + timedelta(days=MEDICAL_VALID_DAYS) if result == Medical.Result.FIT else None
    med, _ = Medical.objects.update_or_create(
        case=case,
        defaults={"result": result, "clinic": clinic, "slip": slip,
                  "issued_on": issued_on if result == Medical.Result.FIT else None,
                  "expires_on": expires},
    )
    if result == Medical.Result.FIT and case.stage in (VisaCase.Stage.MED_SCHED, VisaCase.Stage.ATTEST, VisaCase.Stage.DOCS):
        case.stage = VisaCase.Stage.MED_OK
        case.save(update_fields=["stage"])
    if result == Medical.Result.UNFIT:
        case.stage = VisaCase.Stage.REJ
        case.cancel_reason = "Medical unfit"
        case.save(update_fields=["stage", "cancel_reason"])
    return med


def medical_alerts(today=None):
    today = today or timezone.localdate()
    rows = []
    for med in Medical.objects.filter(result=Medical.Result.FIT, expires_on__isnull=False).select_related("case"):
        left = (med.expires_on - today).days
        if left <= 30:
            rows.append((med, left))
    return rows


# ------------------------------------------------------------------ custody
@transaction.atomic
def move_passport(passport: Passport, to_loc: str, user=None, note="") -> Passport:
    from .models import CustodyEvent
    if to_loc == Passport.Loc.CLIENT:
        # hard stop: unpaid files stay in vault
        for case in passport.cases.exclude(stage__in=(VisaCase.Stage.DONE, VisaCase.Stage.REJ)):
            if not can_release(case):
                raise DomainError("Unpaid balance or credit lock — passport stays in the vault.")
    prev = passport.location
    passport.location = to_loc
    passport.save(update_fields=["location"])
    CustodyEvent.objects.create(passport=passport, from_loc=prev, to_loc=to_loc, user=user, note=note)
    return passport


def can_release(case: VisaCase) -> bool:
    if case.agent_id:
        agent = case.agent
        if agent.is_locked:
            return False
        if agent.credit_limit > 0 and agent.receivable > agent.credit_limit:
            return False
    for inv in case.invoices.all():
        if inv.balance_due > 0:
            return False
    return True


def assert_download_ok(case: VisaCase) -> None:
    if not can_release(case):
        raise DomainError(
            "Visa PDF / pouch barcode is locked until the file is fully paid "
            "and the sub-agent (if any) is inside their credit limit."
        )


def refresh_agent_lock(agent: SubAgent) -> SubAgent:
    if agent.credit_limit > 0 and agent.receivable > agent.credit_limit:
        agent.is_locked = True
        agent.save(update_fields=["is_locked"])
    elif agent.is_locked and agent.receivable <= agent.credit_limit:
        agent.is_locked = False
        agent.save(update_fields=["is_locked"])
    return agent


# ------------------------------------------------------------------ ledger
@transaction.atomic
def post_journal(*, debit: Account, credit: Account, amount, narration, user=None,
                 case=None, invoice=None, booked_on=None) -> JournalLine:
    amount = money(amount)
    if amount <= 0:
        raise DomainError("Journal amount must be positive.")
    if debit.pk == credit.pk:
        raise DomainError("Debit and credit cannot be the same account.")
    line = JournalLine.objects.create(
        batch=uuid.uuid4(), booked_on=booked_on or timezone.localdate(),
        debit=debit, credit=credit, amount=amount, narration=narration,
        user=user, case=case, invoice=invoice,
    )
    return line


@transaction.atomic
def raise_invoice(*, case: VisaCase, amount, tax=0, discount=0, description="Visa package",
                  due_days=15, user=None) -> Invoice:
    ensure_coa()
    amount, tax, discount = money(amount), money(tax), money(discount)
    if amount <= 0:
        raise DomainError("Invoice amount must be positive.")
    grand = money(amount - discount + tax)
    inv = Invoice.objects.create(
        case=case, client=case.client, agent=case.agent,
        due_on=timezone.localdate() + timedelta(days=due_days),
        subtotal=amount, discount=discount, tax=tax, grand_total=grand,
    )
    InvoiceLine.objects.create(invoice=inv, description=description, account=acct("4010"),
                               unit_price=amount, qty=1, tax_rate=ZERO)
    recv = acct("1040") if case.agent_id else acct("1030")
    post_journal(debit=recv, credit=acct("2010"), amount=grand,
                 narration=f"Invoice {inv.number} unearned retainer",
                 user=user, case=case, invoice=inv)
    if case.agent_id:
        refresh_agent_lock(case.agent)
    log(user, "invoice", inv, inv.number)
    return inv


@transaction.atomic
def take_receipt(*, invoice: Invoice, amount, method="cash", reference="", staff=None, user=None) -> Receipt:
    amount = money(amount)
    if amount <= 0:
        raise DomainError("Receipt must be positive.")
    if amount > invoice.balance_due:
        raise DomainError("Receipt exceeds balance due.")
    cash = acct("1010") if method == "cash" else acct("1020")
    recv = acct("1040") if invoice.agent_id else acct("1030")
    rec = Receipt.objects.create(invoice=invoice, amount=amount, method=method,
                                 reference=reference, collected_by=staff)
    post_journal(debit=cash, credit=recv, amount=amount,
                 narration=f"Receipt {rec.number} against {invoice.number}",
                 user=user, case=invoice.case, invoice=invoice)
    invoice.paid_amount = money(invoice.paid_amount + amount)
    invoice.refresh_status()
    if invoice.agent_id:
        refresh_agent_lock(invoice.agent)
    return rec


@transaction.atomic
def recognize_revenue(invoice: Invoice, user=None) -> Invoice:
    if invoice.revenue_recognized:
        return invoice
    post_journal(debit=acct("2010"), credit=acct("4010"), amount=invoice.grand_total,
                 narration=f"Recognize {invoice.number} — visa issued",
                 user=user, case=invoice.case, invoice=invoice)
    invoice.revenue_recognized = True
    invoice.save(update_fields=["revenue_recognized"])
    return invoice


@transaction.atomic
def petty_out(*, branch, staff, amount, purpose, expense_code="5020", user=None) -> PettyCash:
    amount = money(amount)
    if amount <= 0:
        raise DomainError("Petty cash must be positive.")
    row = PettyCash.objects.create(branch=branch, requested_by=staff, account=acct(expense_code),
                                   amount=amount, purpose=purpose)
    post_journal(debit=acct(expense_code), credit=acct("1010"), amount=amount,
                 narration=purpose, user=user)
    return row


def trial_balance() -> Decimal:
    """Sum of (asset+expense debit bal) minus (liab+rev credit bal) must be 0."""
    ensure_coa()
    total = ZERO
    for a in Account.objects.filter(is_active=True):
        if a.kind in (Account.Kind.ASSET, Account.Kind.DCOST, Account.Kind.OPEX):
            total += a.balance
        else:
            total -= a.balance
    return money(total)


# ------------------------------------------------------------------ HR
@transaction.atomic
def clock_in(staff: Staff) -> Attendance:
    today = timezone.localdate()
    row, created = Attendance.objects.get_or_create(staff=staff, day=today, defaults={"status": "present"})
    if row.check_in:
        raise DomainError("Already clocked in today.")
    row.check_in = timezone.now()
    row.save()
    return row


@transaction.atomic
def clock_out(staff: Staff) -> Attendance:
    row = Attendance.objects.filter(staff=staff, day=timezone.localdate()).first()
    if not row or not row.check_in:
        raise DomainError("Clock in first.")
    if row.check_out:
        raise DomainError("Already clocked out.")
    row.check_out = timezone.now()
    if row.check_out < row.check_in:
        raise DomainError("Clock-out cannot precede clock-in.")
    row.save()
    return row


@transaction.atomic
def request_leave(staff: Staff, start, end, kind=Leave.Kind.CASUAL, reason="") -> Leave:
    if end < start:
        raise DomainError("Leave end cannot precede start.")
    clash = Leave.objects.filter(staff=staff, status__in=(Leave.Status.PENDING, Leave.Status.OK),
                                 start__lte=end, end__gte=start)
    if clash.exists():
        raise DomainError("Leave overlaps an existing request.")
    return Leave.objects.create(staff=staff, start=start, end=end, kind=kind, reason=reason)


@transaction.atomic
def run_payroll(staff: Staff, period: str, housing=0, transport=0, bonus=0, commission=0, deductions=0) -> Payroll:
    base = staff.base_salary
    net = money(base + money(housing) + money(transport) + money(bonus) + money(commission) - money(deductions))
    if net < 0:
        raise DomainError("Net pay cannot be negative.")
    row, _ = Payroll.objects.update_or_create(
        staff=staff, period=period,
        defaults={"base": base, "housing": money(housing), "transport": money(transport),
                  "bonus": money(bonus), "commission": money(commission),
                  "deductions": money(deductions), "net": net, "status": "processed"},
    )
    post_journal(debit=acct("6010"), credit=acct("2030"), amount=net,
                 narration=f"Payroll {staff.code} {period}")
    return row
