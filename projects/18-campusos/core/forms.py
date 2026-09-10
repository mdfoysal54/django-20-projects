"""CampusOS forms."""
from django import forms
from .models import (
    Book, Exam, FeeHead, Guardian, Invoice, Klass, Notice, Route, School, Section,
    Staff, Student, Subject,
)


def _w(form):
    for f in form.fields.values():
        if not isinstance(f.widget, (forms.CheckboxInput,)):
            f.widget.attrs["class"] = "form-control"


class Styled(forms.ModelForm):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _w(self)


class SchoolForm(Styled):
    class Meta:
        model = School
        fields = ["name", "motto", "email", "phone", "address", "theme", "language"]


class StudentForm(Styled):
    class Meta:
        model = Student
        fields = ["first_name", "last_name", "gender", "born_on", "guardian", "section"]


class GuardianForm(Styled):
    class Meta:
        model = Guardian
        fields = ["name", "phone", "email", "relation"]


class InvoiceForm(Styled):
    class Meta:
        model = Invoice
        fields = ["student", "head", "period", "amount", "due_on"]


class ExamForm(Styled):
    class Meta:
        model = Exam
        fields = ["name", "year", "held_on", "max_marks"]


class BookForm(Styled):
    class Meta:
        model = Book
        fields = ["title", "author", "isbn", "copies"]


class NoticeForm(Styled):
    class Meta:
        model = Notice
        fields = ["title", "body", "audience"]


class RouteForm(Styled):
    class Meta:
        model = Route
        fields = ["name", "vehicle", "driver", "fee"]


class PayForm(forms.Form):
    amount = forms.DecimalField(min_value=0.01, decimal_places=2, max_digits=12)
    method = forms.ChoiceField(choices=[("cash", "Cash"), ("bkash", "bKash"), ("bank", "Bank")])

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _w(self)
