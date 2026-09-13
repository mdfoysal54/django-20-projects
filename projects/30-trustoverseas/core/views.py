"""Trust Overseas Ltd — public site, portals, and staff ERP."""
from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AgentForm, AttestationForm, CaseOpenForm, ClientForm, CustodyForm, DocumentForm,
    InvoiceForm, LeadForm, LeaveForm, MedicalForm, PassportForm, PayrollForm, PettyForm,
    PortalForm, ProfileForm, ReceiptForm, TrackForm,
)
from .models import (
    ZERO, Account, Attendance, Attestation, AuditLog, Branch, CaseDocument, Client,
    Invoice, JournalLine, Lead, Leave, Medical, Passport, Payroll, PettyCash,
    PortalSubmission, Receipt, Staff, SubAgent, VisaCase,
)
from .services import (
    DomainError, LEGAL, advance_case, assert_download_ok, clock_in, clock_out,
    ensure_coa, medical_alerts, move_passport, open_case, petty_out, raise_invoice,
    record_medical, request_leave, run_payroll, take_receipt, trial_balance,
)

NAV = [
    ("Command", [("dashboard", "Dashboard")]),
    ("Pipeline", [("lead_list", "Leads"), ("client_list", "Clients"),
                  ("agent_list", "Sub-agents"), ("case_list", "Cases")]),
    ("Compliance", [("vault", "Passport vault"), ("gamca_board", "GAMCA / Wafid"),
                    ("attest_board", "Attestation"), ("portal_board", "GCC portals")]),
    ("Ledger", [("invoice_list", "Invoices"), ("ledger", "Journal"),
                ("trial", "Trial balance"), ("petty", "Petty cash"), ("coa", "Chart of accounts")]),
    ("People", [("hr_desk", "HR desk"), ("hr_clock", "Clock"), ("hr_leave", "Leave"),
                ("hr_payroll", "Payroll"), ("audit", "Audit log")]),
]

DESTINATIONS = [
    ("SAU", "Saudi Arabia", "Qiwa · Enjaz · GAMCA/Wafid", "Work, Umrah, family"),
    ("ARE", "United Arab Emirates", "MOHRE · ICP · GDRFA", "Work, visit, golden"),
    ("QAT", "Qatar", "Metrash2", "Work and family"),
    ("KWT", "Kuwait", "PAM / Manpower", "Work and domestic"),
    ("BHR", "Bahrain", "LMRA", "Work and visit"),
    ("OMN", "Oman", "InvestEasy / ROP", "Work and resident"),
    ("MYS", "Malaysia", "EMGS / Immigration", "Work and student"),
]


def _staff_of(user):
    return getattr(user, "staff", None) if getattr(user, "is_authenticated", False) else None


def staff_required(view):
    @wraps(view)
    @login_required
    def inner(request, *a, **k):
        role = getattr(request, "user", None)
        if _staff_of(role) or (role and role.is_staff):
            return view(request, *a, **k)
        if hasattr(role, "client_profile"):
            messages.info(request, "That desk is for Trust staff. Opening your client portal.")
            return redirect("portal")
        if hasattr(role, "agent_desk"):
            messages.info(request, "That desk is for Trust staff. Opening your agent desk.")
            return redirect("agent_desk")
        messages.error(request, "Staff desk only.")
        return redirect("home")
    return inner


def _ctx(request, **extra):
    extra.setdefault("nav", NAV)
    extra.setdefault("today", timezone.localdate())
    extra.setdefault("staff", _staff_of(request.user))
    return extra


def _page(qs, request, per=20):
    return Paginator(qs, per).get_page(request.GET.get("page"))


def _flash_err(request, exc: Exception):
    messages.error(request, str(exc))


# ================================================================= public
def index(request):
    return render(request, "trust/landing.html", {
        "destinations": DESTINATIONS,
        "open_files": VisaCase.objects.exclude(stage__in=("done", "rej")).count(),
        "issued": VisaCase.objects.filter(stage__in=("iss", "fly", "arr", "post", "done")).count(),
    })


def destinations(request):
    return render(request, "trust/destinations.html", {"destinations": DESTINATIONS})


def about(request):
    return render(request, "trust/about.html", {"branch": Branch.hq() if Branch.objects.exists() else None})


def contact(request):
    if request.method == "POST":
        form = LeadForm(request.POST)
        if form.is_valid():
            lead = form.save()
            messages.success(request, f"Thank you {lead.name}. A counsellor will call {lead.phone}.")
            return redirect("contact")
    else:
        form = LeadForm()
    return render(request, "trust/contact.html", {"form": form})


def track(request):
    case = None
    form = TrackForm(request.GET or None)
    if request.GET and form.is_valid():
        number = form.cleaned_data["number"].strip()
        pin = form.cleaned_data["pin"].strip()
        found = VisaCase.objects.filter(number__iexact=number).select_related("client", "passport").first()
        if found and found.client.pin and found.client.pin == pin:
            case = found
        else:
            messages.error(request, "No file matches that number and PIN.")
    return render(request, "trust/track.html", {"form": form, "case": case})


# ================================================================= portals
@login_required
def client_portal(request):
    profile = getattr(request.user, "client_profile", None)
    if profile is None:
        messages.error(request, "This login is not linked to a client file.")
        return redirect("home")
    cases = profile.cases.select_related("passport").all()
    invoices = profile.invoices.select_related("case").all()
    return render(request, "trust/portal.html", {"client": profile, "cases": cases, "invoices": invoices})


@login_required
def agent_desk(request):
    agent = getattr(request.user, "agent_desk", None)
    if agent is None:
        messages.error(request, "This login is not linked to a sub-agent.")
        return redirect("home")
    cases = agent.cases.select_related("client", "passport").all()
    invoices = agent.invoices.select_related("case", "client").all()
    locked = []
    from .services import can_release
    for c in cases:
        if not can_release(c):
            locked.append(c.number)
    return render(request, "trust/agent.html", {
        "agent": agent, "cases": cases, "invoices": invoices, "locked": locked,
    })


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile saved.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "trust/form.html", _ctx(request, form=form, title="My profile", action=""))


# ================================================================= desk
@staff_required
def dashboard(request):
    today = timezone.localdate()
    open_qs = VisaCase.objects.exclude(stage__in=(VisaCase.Stage.DONE, VisaCase.Stage.REJ))
    alerts = medical_alerts(today)
    expiring = [p for p in Passport.objects.select_related("client") if p.days_left < 220]
    sla = open_qs.filter(sla_date__lt=today)
    due = Invoice.objects.exclude(status=Invoice.Status.PAID)
    due_total = due.aggregate(s=Sum("grand_total"))["s"] or ZERO
    paid_total = due.aggregate(s=Sum("paid_amount"))["s"] or ZERO
    return render(request, "trust/dashboard.html", _ctx(
        request,
        open_count=open_qs.count(),
        issued_mtd=VisaCase.objects.filter(stage=VisaCase.Stage.ISSUED).count(),
        leads_new=Lead.objects.filter(status=Lead.Status.NEW).count(),
        receivable=due_total - paid_total,
        recent=open_qs.select_related("client")[:8],
        alerts=alerts[:8],
        expiring=expiring[:8],
        sla=sla.select_related("client")[:8],
        locked_agents=SubAgent.objects.filter(is_locked=True),
    ))


# ================================================================= CRM
@staff_required
def lead_list(request):
    qs = Lead.objects.all().order_by("-id")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    return render(request, "trust/leads.html", _ctx(request, page=_page(qs, request), q=q))


@staff_required
def lead_new(request):
    if request.method == "POST":
        form = LeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Inquiry logged.")
            return redirect("lead_list")
    else:
        form = LeadForm()
    return render(request, "trust/form.html", _ctx(request, form=form, title="New inquiry"))


@staff_required
@require_POST
def lead_win(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    lead.status = Lead.Status.WON
    lead.save(update_fields=["status"])
    messages.success(request, f"{lead.name} marked won — open a client file next.")
    return redirect("client_create")


@staff_required
def client_list(request):
    qs = Client.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q)
                       | Q(phone__icontains=q) | Q(code__icontains=q))
    page = _page(qs, request)
    return render(request, "trust/clients.html", _ctx(request, page=page, q=q))


@staff_required
def client_form(request, code=None):
    obj = get_object_or_404(Client, code=code) if code else None
    if request.method == "POST":
        form = ClientForm(request.POST, instance=obj)
        if form.is_valid():
            saved = form.save()
            messages.success(request, f"Client {saved.code} saved.")
            return redirect(saved)
    else:
        form = ClientForm(instance=obj)
    return render(request, "trust/form.html", _ctx(
        request, form=form, title="Edit client" if obj else "New client"))


@staff_required
def client_detail(request, code):
    client = get_object_or_404(Client, code=code)
    return render(request, "trust/client_detail.html", _ctx(request, client=client))


@staff_required
def agent_list(request):
    agents = SubAgent.objects.all()
    return render(request, "trust/agents.html", _ctx(request, agents=agents))


@staff_required
def agent_form(request, pk=None):
    obj = get_object_or_404(SubAgent, pk=pk) if pk else None
    if request.method == "POST":
        form = AgentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Sub-agent saved.")
            return redirect("agent_list")
    else:
        form = AgentForm(instance=obj)
    return render(request, "trust/form.html", _ctx(
        request, form=form, title="Edit sub-agent" if obj else "New sub-agent"))


# ================================================================= vault
@staff_required
def vault(request):
    qs = Passport.objects.select_related("client").order_by("location", "expiry_date")
    loc = request.GET.get("loc")
    if loc:
        qs = qs.filter(location=loc)
    return render(request, "trust/vault.html", _ctx(
        request, passports=qs, loc=loc, locations=Passport.Loc.choices))


@staff_required
def passport_form(request):
    if request.method == "POST":
        form = PassportForm(request.POST)
        if form.is_valid():
            p = form.save()
            messages.success(request, f"Passport {p.number} in the vault.")
            return redirect(p)
    else:
        initial = {}
        code = request.GET.get("client")
        if code:
            c = Client.objects.filter(code=code).first()
            if c:
                initial["client"] = c
        form = PassportForm(initial=initial)
    return render(request, "trust/form.html", _ctx(request, form=form, title="Lodge passport"))


@staff_required
def passport_detail(request, number):
    passport = get_object_or_404(Passport, number=number)
    return render(request, "trust/passport_detail.html", _ctx(
        request, passport=passport, form=CustodyForm()))


@staff_required
@require_POST
def passport_move(request, number):
    passport = get_object_or_404(Passport, number=number)
    form = CustodyForm(request.POST)
    if form.is_valid():
        try:
            move_passport(passport, form.cleaned_data["to_loc"], user=request.user,
                          note=form.cleaned_data.get("note") or "")
            messages.success(request, f"Passport moved to {form.cleaned_data['to_loc']}.")
        except DomainError as exc:
            _flash_err(request, exc)
    return redirect(passport)


# ================================================================= cases
@staff_required
def case_list(request):
    qs = VisaCase.objects.select_related("client", "passport", "officer")
    stage = request.GET.get("stage")
    dest = request.GET.get("dest")
    q = request.GET.get("q", "").strip()
    if stage:
        qs = qs.filter(stage=stage)
    if dest:
        qs = qs.filter(destination=dest)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(client__first_name__icontains=q)
                       | Q(client__last_name__icontains=q) | Q(passport__number__icontains=q))
    return render(request, "trust/cases.html", _ctx(
        request, page=_page(qs, request), stage=stage, dest=dest, q=q,
        stages=VisaCase.Stage.choices, destinations=DESTINATIONS))


@staff_required
def case_open(request):
    if request.method == "POST":
        form = CaseOpenForm(request.POST)
        if form.is_valid():
            try:
                case = open_case(
                    client=form.cleaned_data["client"],
                    passport=form.cleaned_data["passport"],
                    branch=_staff_of(request.user).branch if _staff_of(request.user) else Branch.hq(),
                    destination=form.cleaned_data["destination"],
                    visa_category=form.cleaned_data["visa_category"],
                    job_title=form.cleaned_data.get("job_title") or "",
                    agent=form.cleaned_data.get("agent"),
                    officer=_staff_of(request.user),
                    user=request.user,
                )
                messages.success(request, f"File {case.number} opened.")
                return redirect(case)
            except DomainError as exc:
                _flash_err(request, exc)
    else:
        form = CaseOpenForm()
    return render(request, "trust/form.html", _ctx(request, form=form, title="Open a visa file"))


@staff_required
def case_detail(request, number):
    case = get_object_or_404(
        VisaCase.objects.select_related("client", "passport", "agent", "officer", "branch"),
        number=number,
    )
    from .services import can_release
    nxt = sorted(LEGAL.get(case.stage, set()))
    return render(request, "trust/case_detail.html", _ctx(
        request, case=case, next_stages=nxt, can_release=can_release(case),
        med_form=MedicalForm(), inv_form=InvoiceForm(), doc_form=DocumentForm(),
        attest_form=AttestationForm(), portal_form=PortalForm(),
    ))


@staff_required
@require_POST
def case_advance(request, number):
    case = get_object_or_404(VisaCase, number=number)
    to_stage = request.POST.get("to_stage", "")
    try:
        advance_case(case, to_stage, user=request.user)
        messages.success(request, f"{case.number} → {case.get_stage_display()}.")
    except DomainError as exc:
        _flash_err(request, exc)
    return redirect(case)


@staff_required
@require_POST
def case_document(request, number):
    case = get_object_or_404(VisaCase, number=number)
    form = DocumentForm(request.POST)
    if form.is_valid():
        CaseDocument.objects.create(case=case, **form.cleaned_data)
        messages.success(request, "Document logged.")
    return redirect(case)


@staff_required
@require_POST
def case_medical(request, number):
    case = get_object_or_404(VisaCase, number=number)
    form = MedicalForm(request.POST)
    if form.is_valid():
        record_medical(
            case, result=form.cleaned_data["result"],
            clinic=form.cleaned_data.get("clinic") or "",
            slip=form.cleaned_data.get("slip") or "",
            issued_on=form.cleaned_data.get("issued_on"),
        )
        messages.success(request, "Medical result saved.")
    return redirect(case)


@staff_required
@require_POST
def case_attest(request, number):
    case = get_object_or_404(VisaCase, number=number)
    form = AttestationForm(request.POST)
    if form.is_valid():
        form.instance.case = case
        form.save()
        messages.success(request, "Attestation step added.")
    return redirect(case)


@staff_required
@require_POST
def case_portal(request, number):
    case = get_object_or_404(VisaCase, number=number)
    form = PortalForm(request.POST)
    if form.is_valid():
        row = form.save(commit=False)
        row.case = case
        row.submitted_on = timezone.now()
        row.save()
        messages.success(request, f"{row.portal} submission logged.")
    return redirect(case)


@staff_required
@require_POST
def case_invoice(request, number):
    case = get_object_or_404(VisaCase, number=number)
    form = InvoiceForm(request.POST)
    if form.is_valid():
        try:
            inv = raise_invoice(
                case=case, amount=form.cleaned_data["amount"],
                tax=form.cleaned_data.get("tax") or 0,
                discount=form.cleaned_data.get("discount") or 0,
                description=form.cleaned_data.get("description") or "Visa package",
                due_days=form.cleaned_data.get("due_days") or 15,
                user=request.user,
            )
            messages.success(request, f"Invoice {inv.number} raised (unearned until visa issued).")
        except DomainError as exc:
            _flash_err(request, exc)
    return redirect(case)


@login_required
def visa_download(request, number):
    case = get_object_or_404(VisaCase, number=number)
    # staff, owning client, or owning agent may attempt; lock still applies
    staff = _staff_of(request.user)
    client = getattr(request.user, "client_profile", None)
    agent = getattr(request.user, "agent_desk", None)
    allowed = bool(staff or request.user.is_staff
                   or (client and client.pk == case.client_id)
                   or (agent and agent.pk == case.agent_id))
    if not allowed:
        return HttpResponseForbidden("Not your file.")
    try:
        assert_download_ok(case)
    except DomainError as exc:
        return HttpResponseForbidden(str(exc))
    body = (
        f"TRUST OVERSEAS LTD — VISA POUCH\n"
        f"File: {case.number}\nClient: {case.client.full_name}\n"
        f"Passport: {case.passport.number}\nDestination: {case.destination}\n"
        f"Stage: {case.get_stage_display()}\nBarcode: *{case.number}*\n"
    )
    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{case.number}-pouch.txt"'
    return resp


# ================================================================= boards
@staff_required
def gamca_board(request):
    rows = Medical.objects.select_related("case", "case__client").order_by("expires_on")
    return render(request, "trust/gamca.html", _ctx(request, rows=rows, alerts=medical_alerts()))


@staff_required
def attest_board(request):
    rows = Attestation.objects.select_related("case", "case__client").order_by("cleared", "order")
    return render(request, "trust/attest.html", _ctx(request, rows=rows))


@staff_required
def portal_board(request):
    rows = PortalSubmission.objects.select_related("case", "case__client").order_by("-id")
    return render(request, "trust/portals.html", _ctx(request, rows=rows))


# ================================================================= accounts
@staff_required
def invoice_list(request):
    qs = Invoice.objects.select_related("client", "case").order_by("-id")
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    return render(request, "trust/invoices.html", _ctx(
        request, page=_page(qs, request), status=status))


@staff_required
def invoice_detail(request, number):
    inv = get_object_or_404(Invoice, number=number)
    return render(request, "trust/invoice_detail.html", _ctx(
        request, invoice=inv, form=ReceiptForm()))


@staff_required
@require_POST
def invoice_pay(request, number):
    inv = get_object_or_404(Invoice, number=number)
    form = ReceiptForm(request.POST)
    if form.is_valid():
        try:
            rec = take_receipt(
                invoice=inv, amount=form.cleaned_data["amount"],
                method=form.cleaned_data["method"],
                reference=form.cleaned_data.get("reference") or "",
                staff=_staff_of(request.user), user=request.user,
            )
            messages.success(request, f"Receipt {rec.number} posted.")
        except DomainError as exc:
            _flash_err(request, exc)
    return redirect(inv)


@staff_required
def ledger(request):
    qs = JournalLine.objects.select_related("debit", "credit", "case")
    return render(request, "trust/ledger.html", _ctx(request, page=_page(qs, request, 40)))


@staff_required
def trial(request):
    ensure_coa()
    accounts = Account.objects.filter(is_active=True).order_by("code")
    return render(request, "trust/trial.html", _ctx(
        request, accounts=accounts, residual=trial_balance()))


@staff_required
def petty(request):
    if request.method == "POST":
        form = PettyForm(request.POST)
        if form.is_valid():
            staff = _staff_of(request.user)
            try:
                petty_out(
                    branch=staff.branch if staff else Branch.hq(),
                    staff=staff, amount=form.cleaned_data["amount"],
                    purpose=form.cleaned_data["purpose"],
                    expense_code=form.cleaned_data["expense_code"],
                    user=request.user,
                )
                messages.success(request, "Petty cash posted.")
                return redirect("petty")
            except DomainError as exc:
                _flash_err(request, exc)
    else:
        form = PettyForm()
    rows = PettyCash.objects.select_related("requested_by", "account").order_by("-id")[:40]
    return render(request, "trust/petty.html", _ctx(request, form=form, rows=rows))


@staff_required
def coa(request):
    ensure_coa()
    return render(request, "trust/coa.html", _ctx(
        request, accounts=Account.objects.filter(is_active=True).order_by("code")))


@staff_required
def audit(request):
    return render(request, "trust/audit.html", _ctx(
        request, page=_page(AuditLog.objects.select_related("user"), request, 40)))


# ================================================================= HR
@staff_required
def hr_desk(request):
    staff = Staff.objects.select_related("user", "branch").all()
    today = timezone.localdate()
    present = Attendance.objects.filter(day=today, status="present").count()
    return render(request, "trust/hr.html", _ctx(
        request, people=staff, present=present,
        pending_leave=Leave.objects.filter(status=Leave.Status.PENDING).select_related("staff"),
    ))


@staff_required
def hr_clock(request):
    staff = _staff_of(request.user)
    if request.method == "POST" and staff:
        action = request.POST.get("action")
        try:
            if action == "in":
                clock_in(staff)
                messages.success(request, "Clocked in.")
            else:
                clock_out(staff)
                messages.success(request, "Clocked out.")
        except DomainError as exc:
            _flash_err(request, exc)
        return redirect("hr_clock")
    today = Attendance.objects.filter(day=timezone.localdate()).select_related("staff")
    return render(request, "trust/clock.html", _ctx(request, today=today, me=staff))


@staff_required
def hr_leave(request):
    staff = _staff_of(request.user)
    if request.method == "POST" and staff:
        form = LeaveForm(request.POST)
        if form.is_valid():
            try:
                request_leave(staff, form.cleaned_data["start"], form.cleaned_data["end"],
                              kind=form.cleaned_data["kind"], reason=form.cleaned_data.get("reason") or "")
                messages.success(request, "Leave requested.")
                return redirect("hr_leave")
            except DomainError as exc:
                _flash_err(request, exc)
    else:
        form = LeaveForm()
    rows = Leave.objects.select_related("staff").order_by("-id")
    return render(request, "trust/leave.html", _ctx(request, form=form, rows=rows))


@staff_required
@require_POST
def hr_leave_decide(request, pk, decision):
    row = get_object_or_404(Leave, pk=pk)
    if decision == "ok":
        row.status = Leave.Status.OK
    else:
        row.status = Leave.Status.NO
    row.save(update_fields=["status"])
    messages.success(request, f"Leave {row.get_status_display().lower()}.")
    return redirect("hr_leave")


@staff_required
def hr_payroll(request):
    rows = Payroll.objects.select_related("staff").order_by("-period", "-id")
    return render(request, "trust/payroll.html", _ctx(
        request, rows=rows, people=Staff.objects.filter(status=Staff.Status.ACTIVE),
        form=PayrollForm(initial={"period": timezone.localdate().strftime("%Y-%m")}),
    ))


@staff_required
@require_POST
def hr_run_pay(request, code):
    staff = get_object_or_404(Staff, code=code)
    form = PayrollForm(request.POST)
    if form.is_valid():
        try:
            row = run_payroll(
                staff, form.cleaned_data["period"],
                housing=form.cleaned_data.get("housing") or 0,
                transport=form.cleaned_data.get("transport") or 0,
                bonus=form.cleaned_data.get("bonus") or 0,
                commission=form.cleaned_data.get("commission") or 0,
                deductions=form.cleaned_data.get("deductions") or 0,
            )
            messages.success(request, f"Payslip {staff.code} {row.period} net ৳ {row.net}.")
        except DomainError as exc:
            _flash_err(request, exc)
    return redirect("hr_payroll")
