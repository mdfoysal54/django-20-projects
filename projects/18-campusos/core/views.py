"""CampusOS views."""
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BookForm, ExamForm, GuardianForm, InvoiceForm, NoticeForm, PayForm, RouteForm, SchoolForm, StudentForm
from .models import (
    ZERO, AcademicYear, Attendance, Book, Exam, FeeHead, Guardian, Invoice, Klass,
    Loan, Notice, Period, Rider, Route, School, Score, Section, SmsLog, Staff,
    Student, Subject, money,
)
from .services import (
    DomainError, attendance_rate, board_student, collect_fee, enrol, issue_book,
    mark_register, record_score, return_book, send_sms,
)

NAV = [
    ("Campus", [("dashboard", "Dashboard"), ("student_list", "Students"), ("admissions", "Admissions")]),
    ("Academics", [("attendance", "Attendance"), ("exam_list", "Exams"), ("timetable", "Timetable")]),
    ("Office", [("fee_list", "Fees"), ("staff_list", "Staff"), ("library", "Library"),
                ("transport", "Transport"), ("notices", "Notices")]),
    ("Reports", [("report_fees", "Fee dues"), ("report_results", "Results"),
                 ("report_attendance", "Attendance %")]),
]


def _ctx(request, **extra):
    extra.setdefault("school", School.get())
    extra.setdefault("nav", NAV)
    extra.setdefault("today", timezone.localdate())
    return extra


def index(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "campus/landing.html", _ctx(request))


@login_required
def dashboard(request):
    students = Student.objects.filter(status=Student.Status.ENROLLED)
    open_fees = Invoice.objects.exclude(status__in=(Invoice.Status.PAID, Invoice.Status.VOID))
    return render(request, "campus/dashboard.html", _ctx(request,
        n_students=students.count(), n_applicants=Student.objects.filter(status=Student.Status.APPLICANT).count(),
        due=money(sum((i.balance for i in open_fees), ZERO)),
        notices=Notice.objects.order_by("-published_on")[:5],
        recent=students.select_related("section", "guardian")[:8],
    ))


@login_required
def student_list(request):
    rows = Student.objects.select_related("section", "guardian")
    q = request.GET.get("q", "").strip()
    if q:
        rows = rows.filter(first_name__icontains=q) | rows.filter(last_name__icontains=q) | rows.filter(number__icontains=q)
    return render(request, "campus/students.html", _ctx(request, rows=rows, q=q))


@login_required
def student_form(request):
    if request.method == "POST":
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save()
            messages.success(request, f"{student.full_name} saved as {student.number}.")
            return redirect(student)
    else:
        form = StudentForm()
    return render(request, "campus/form.html", _ctx(request, form=form, title="New student"))


@login_required
def student_detail(request, number):
    student = get_object_or_404(Student, number=number)
    return render(request, "campus/student.html", _ctx(
        request, student=student, invoices=student.invoices.all()[:12],
        rate=attendance_rate(student), scores=student.scores.select_related("exam", "subject")[:12],
        sections=Section.objects.select_related("klass"),
    ))


@login_required
@require_POST
def student_enrol(request, number):
    student = get_object_or_404(Student, number=number)
    section = get_object_or_404(Section, pk=request.POST.get("section"))
    try:
        enrol(student, section)
        messages.success(request, f"{student.full_name} enrolled in {section}.")
    except DomainError as exc:
        messages.error(request, str(exc))
    return redirect(student)


@login_required
def admissions(request):
    rows = Student.objects.filter(status=Student.Status.APPLICANT)
    return render(request, "campus/students.html", _ctx(request, rows=rows, q="", admissions=True))


@login_required
def guardian_list(request):
    if request.method == "POST":
        form = GuardianForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Guardian saved.")
            return redirect("guardian_list")
    else:
        form = GuardianForm()
    return render(request, "campus/simple.html", _ctx(request, form=form, rows=Guardian.objects.all(), title="Guardians"))


@login_required
def fee_list(request):
    rows = Invoice.objects.select_related("student", "head").order_by("-id")
    return render(request, "campus/fees.html", _ctx(request, rows=rows))


@login_required
def fee_create(request):
    if request.method == "POST":
        form = InvoiceForm(request.POST)
        if form.is_valid():
            inv = form.save()
            messages.success(request, f"{inv.number} raised.")
            return redirect(inv)
    else:
        form = InvoiceForm(initial={"period": timezone.localdate().strftime("%Y-%m"),
                                    "due_on": timezone.localdate() + timedelta(days=10)})
    return render(request, "campus/form.html", _ctx(request, form=form, title="Raise a fee"))


@login_required
def invoice_detail(request, number):
    invoice = get_object_or_404(Invoice, number=number)
    return render(request, "campus/invoice.html", _ctx(request, invoice=invoice, form=PayForm()))


@login_required
@require_POST
def invoice_pay(request, number):
    invoice = get_object_or_404(Invoice, number=number)
    form = PayForm(request.POST)
    if form.is_valid():
        try:
            collect_fee(invoice, form.cleaned_data["amount"], form.cleaned_data["method"], request.user)
            messages.success(request, "Payment recorded.")
        except DomainError as exc:
            messages.error(request, str(exc))
    return redirect(invoice)


@login_required
def attendance(request):
    section = Section.objects.select_related("klass").first()
    if request.GET.get("section"):
        section = get_object_or_404(Section, pk=request.GET["section"])
    day = request.GET.get("day") or timezone.localdate().isoformat()
    if request.method == "POST" and section:
        marks = {int(k.split("_")[1]): v for k, v in request.POST.items() if k.startswith("m_")}
        n = mark_register(section, day, marks)
        messages.success(request, f"Register saved for {n} students.")
        return redirect(f"{request.path}?section={section.pk}&day={day}")
    students = section.students.filter(status=Student.Status.ENROLLED) if section else []
    existing = {a.student_id: a.mark for a in Attendance.objects.filter(section=section, day=day)} if section else {}
    return render(request, "campus/attendance.html", _ctx(
        request, sections=Section.objects.select_related("klass"), section=section,
        students=students, day=day, existing=existing, marks=Attendance.Mark.choices,
    ))


@login_required
def exam_list(request):
    if request.method == "POST":
        form = ExamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Exam saved.")
            return redirect("exam_list")
    else:
        form = ExamForm()
    return render(request, "campus/exams.html", _ctx(request, rows=Exam.objects.select_related("year"), form=form))


@login_required
def exam_detail(request, pk):
    exam = get_object_or_404(Exam, pk=pk)
    if request.method == "POST":
        student = get_object_or_404(Student, pk=request.POST.get("student"))
        subject = get_object_or_404(Subject, pk=request.POST.get("subject"))
        try:
            record_score(exam, student, subject, request.POST.get("marks") or "0")
            messages.success(request, "Score saved.")
        except DomainError as exc:
            messages.error(request, str(exc))
        return redirect(exam)
    return render(request, "campus/exam.html", _ctx(
        request, exam=exam, scores=exam.scores.select_related("student", "subject"),
        students=Student.objects.filter(status=Student.Status.ENROLLED),
        subjects=Subject.objects.all(),
    ))


@login_required
def timetable(request):
    section = Section.objects.first()
    if request.GET.get("section"):
        section = get_object_or_404(Section, pk=request.GET["section"])
    periods = Period.objects.filter(section=section).select_related("subject", "teacher") if section else []
    grid = {}
    for p in periods:
        grid.setdefault(p.weekday, {})[p.slot] = p
    return render(request, "campus/timetable.html", _ctx(
        request, section=section, sections=Section.objects.select_related("klass"),
        grid=grid, days=["Mon", "Tue", "Wed", "Thu", "Fri"], slots=range(1, 7),
    ))


@login_required
def staff_list(request):
    return render(request, "campus/staff.html", _ctx(request, rows=Staff.objects.select_related("user")))


@login_required
def library(request):
    if request.method == "POST" and request.POST.get("intent") == "book":
        form = BookForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Book catalogued.")
            return redirect("library")
    else:
        form = BookForm()
    return render(request, "campus/library.html", _ctx(
        request, books=Book.objects.all(), form=form,
        loans=Loan.objects.filter(returned_on__isnull=True).select_related("book", "student"),
        students=Student.objects.filter(status=Student.Status.ENROLLED),
    ))


@login_required
@require_POST
def loan_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    student = get_object_or_404(Student, pk=request.POST.get("student"))
    try:
        issue_book(book, student)
        messages.success(request, f"{book.title} issued to {student}.")
    except DomainError as exc:
        messages.error(request, str(exc))
    return redirect("library")


@login_required
@require_POST
def loan_return(request, pk):
    loan = get_object_or_404(Loan, pk=pk)
    try:
        return_book(loan)
        messages.success(request, "Book returned.")
    except DomainError as exc:
        messages.error(request, str(exc))
    return redirect("library")


@login_required
def transport(request):
    if request.method == "POST" and request.POST.get("intent") == "route":
        form = RouteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Route saved.")
            return redirect("transport")
    elif request.method == "POST":
        student = get_object_or_404(Student, pk=request.POST.get("student"))
        route = get_object_or_404(Route, pk=request.POST.get("route"))
        board_student(student, route)
        messages.success(request, f"{student} boarded {route}.")
        return redirect("transport")
    return render(request, "campus/transport.html", _ctx(
        request, routes=Route.objects.all(), form=RouteForm(),
        students=Student.objects.filter(status=Student.Status.ENROLLED),
        riders=Rider.objects.select_related("student", "route"),
    ))


@login_required
def notices(request):
    if request.method == "POST":
        form = NoticeForm(request.POST)
        if form.is_valid():
            n = form.save(commit=False)
            n.author = request.user
            n.save()
            messages.success(request, "Notice published.")
            return redirect("notices")
    else:
        form = NoticeForm()
    return render(request, "campus/notices.html", _ctx(request, form=form, rows=Notice.objects.all()))


@login_required
def report_fees(request):
    rows = Invoice.objects.exclude(status__in=(Invoice.Status.PAID, Invoice.Status.VOID)).select_related("student")
    return render(request, "campus/report.html", _ctx(request, title="Outstanding fees", rows=rows, kind="fees",
                                                      total=money(sum((r.balance for r in rows), ZERO))))


@login_required
def report_results(request):
    exam = Exam.objects.order_by("-held_on").first()
    scores = exam.scores.select_related("student", "subject") if exam else []
    return render(request, "campus/report.html", _ctx(request, title="Results", exam=exam, scores=scores, kind="results"))


@login_required
def report_attendance(request):
    rows = [(s, attendance_rate(s)) for s in Student.objects.filter(status=Student.Status.ENROLLED)[:80]]
    return render(request, "campus/report.html", _ctx(request, title="Attendance %", rows=rows, kind="att"))


@login_required
def sms_list(request):
    if request.method == "POST":
        send_sms(request.POST.get("to") or "", request.POST.get("body") or "")
        messages.success(request, "SMS logged.")
        return redirect("sms_list")
    return render(request, "campus/sms.html", _ctx(request, rows=SmsLog.objects.all()[:40]))


@login_required
def settings_hub(request):
    school = School.get()
    if request.method == "POST":
        form = SchoolForm(request.POST, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "School saved.")
            return redirect("settings_hub")
    else:
        form = SchoolForm(instance=school)
    return render(request, "campus/form.html", _ctx(request, form=form, title="School"))


@login_required
def profile(request):
    from .models import Profile
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        profile.theme = request.POST.get("theme") or profile.theme
        profile.language = request.POST.get("language") or profile.language
        profile.phone = request.POST.get("phone") or profile.phone
        profile.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")
    return render(request, "account/profile.html", _ctx(request, profile=profile))
