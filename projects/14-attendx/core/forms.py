"""AttendX forms."""
from django import forms

from .models import AttendanceRecord, Cohort, Session


class CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name", "subject", "room", "meeting_note", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "CS-101 — Intro to Programming"}),
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Computer Science"}),
            "room": forms.TextInput(attrs={"class": "form-control", "placeholder": "Lab 3"}),
            "meeting_note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Sun & Tue, 10:00–11:30"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Give the cohort a clearer name (3+ characters).")
        return name


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["date", "topic", "starts_at", "ends_at", "status", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "topic": forms.TextInput(attrs={"class": "form-control", "placeholder": "Recursion and the call stack"}),
            "starts_at": forms.TimeInput(attrs={"class": "form-control", "type": "time"}, format="%H:%M"),
            "ends_at": forms.TimeInput(attrs={"class": "form-control", "type": "time"}, format="%H:%M"),
            "status": forms.Select(attrs={"class": "form-control"}),
            "note": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]
        for f in ("starts_at", "ends_at"):
            self.fields[f].input_formats = ["%H:%M"]
            self.fields[f].required = False

    def clean_date(self):
        from django.utils import timezone
        value = self.cleaned_data["date"]
        if value > timezone.localdate() + __import__("datetime").timedelta(days=365):
            raise forms.ValidationError("That date is more than a year away.")
        return value

    def clean(self):
        data = super().clean()
        start, end = data.get("starts_at"), data.get("ends_at")
        if start and end and end <= start:
            self.add_error("ends_at", "The session must end after it starts.")
        return data


class JoinForm(forms.Form):
    code = forms.CharField(max_length=8, widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "e.g. K7M2QP", "autocomplete": "off"}))

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class RegisterForm(forms.Form):
    """One page of radio buttons for a whole class register."""

    def __init__(self, *args, cohort=None, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = session
        existing = {}
        if session is not None:
            existing = {r.student_id: r for r in session.records.all()}
        self.fields_by_student = {}
        if cohort is not None:
            choices = AttendanceRecord.Status.choices
            for enrollment in cohort.enrollments.filter(active=True).select_related("student"):
                student = enrollment.student
                name = f"student_{student.pk}"
                current = existing.get(student.pk)
                self.fields[name] = forms.ChoiceField(
                    choices=choices, required=False,
                    initial=current.status if current else AttendanceRecord.Status.PRESENT,
                    widget=forms.RadioSelect(attrs={"class": "status-radio"}),
                )
                self.fields_by_student[name] = student

    def selections(self):
        """Yield (student, status) for every field the teacher actually submitted."""
        for name, student in self.fields_by_student.items():
            value = self.cleaned_data.get(name)
            if value:
                yield student, value
