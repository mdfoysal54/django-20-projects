"""CampusOS domain services."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import (
    ZERO, Attendance, Invoice, Loan, Payment, Rider, Score, SmsLog, Student, money,
)


class DomainError(ValueError):
    pass


@transaction.atomic
def enrol(student: Student, section, day=None) -> Student:
    if section.students.filter(status=Student.Status.ENROLLED).count() >= section.capacity:
        raise DomainError(f"{section} is at capacity ({section.capacity}).")
    student.section = section
    student.status = Student.Status.ENROLLED
    student.admitted_on = day or timezone.localdate()
    student.save(update_fields=["section", "status", "admitted_on"])
    return student


@transaction.atomic
def collect_fee(invoice: Invoice, amount, method="cash", user=None) -> Payment:
    amount = money(amount)
    if invoice.status == Invoice.Status.VOID:
        raise DomainError("A void invoice cannot take payment.")
    if amount <= 0:
        raise DomainError("Payments must be greater than zero.")
    if amount > invoice.balance:
        raise DomainError(f"Overpayment refused — balance is {invoice.balance}.")
    payment = Payment.objects.create(invoice=invoice, amount=amount, method=method, user=user)
    invoice.paid_total = money(invoice.paid_total + amount)
    invoice.refresh_status()
    invoice.save(update_fields=["paid_total", "status"])
    return payment


def mark_register(section, day, marks: dict[int, str], user=None) -> int:
    """marks: student_id -> P/A/L/E. One row per student per day."""
    n = 0
    for student in section.students.filter(status=Student.Status.ENROLLED):
        mark = marks.get(student.pk) or Attendance.Mark.ABSENT
        Attendance.objects.update_or_create(student=student, day=day,
                                            defaults={"mark": mark, "section": section})
        n += 1
    return n


def attendance_rate(student: Student) -> Decimal:
    qs = student.attendance.all()
    total = qs.exclude(mark=Attendance.Mark.EXCUSED).count()
    if total == 0:
        return Decimal("0.00")
    present = qs.filter(mark__in=(Attendance.Mark.PRESENT, Attendance.Mark.LATE)).count()
    return money(Decimal(present) / Decimal(total) * 100)


@transaction.atomic
def record_score(exam, student, subject, marks) -> Score:
    marks = money(marks)
    if marks < 0 or marks > exam.max_marks:
        raise DomainError(f"Marks must be between 0 and {exam.max_marks}.")
    score, _ = Score.objects.update_or_create(exam=exam, student=student, subject=subject,
                                              defaults={"marks": marks})
    return score


@transaction.atomic
def issue_book(book, student, days=14) -> Loan:
    if book.available < 1:
        raise DomainError(f"No copies of {book.title} are on the shelf.")
    if student.status != Student.Status.ENROLLED:
        raise DomainError("Only enrolled students may borrow.")
    return Loan.objects.create(book=book, student=student,
                               due_on=timezone.localdate() + timedelta(days=days))


@transaction.atomic
def return_book(loan: Loan) -> Loan:
    if loan.returned_on:
        raise DomainError("Already returned.")
    loan.returned_on = timezone.localdate()
    loan.save(update_fields=["returned_on"])
    return loan


def board_student(student: Student, route) -> Rider:
    return Rider.objects.update_or_create(student=student, defaults={"route": route})[0]


def send_sms(to, body) -> SmsLog:
    return SmsLog.objects.create(to=to, body=body[:480])
