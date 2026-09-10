"""MedCare forms."""
from django import forms

from .models import Appointment, DoctorAvailability


class BookingForm(forms.Form):
    doctor = forms.IntegerField(widget=forms.HiddenInput)
    starts_at = forms.CharField(widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control",
                                      "placeholder": "Briefly, what's the visit about?"}),
    )

    def clean_starts_at(self):
        from django.utils.dateparse import parse_datetime
        raw = self.cleaned_data["starts_at"]
        value = parse_datetime(raw)
        if value is None:
            raise forms.ValidationError("Pick a slot from the list.")
        return value

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if len(reason) < 5:
            raise forms.ValidationError("Tell the doctor a little more (5+ characters).")
        return reason


class ClinicalNoteForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["clinical_note", "status"]
        widgets = {
            "clinical_note": forms.Textarea(attrs={"class": "form-control", "rows": 4,
                                                   "placeholder": "Findings, prescription, follow-up…"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (Appointment.Status.BOOKED, "Booked"),
            (Appointment.Status.COMPLETED, "Completed"),
            (Appointment.Status.NO_SHOW, "No show"),
        ]


class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = DoctorAvailability
        fields = ["weekday", "start_time", "end_time"]
        widgets = {
            "weekday": forms.Select(attrs={"class": "form-control"}),
            "start_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"class": "form-control", "type": "time"}, format="%H:%M"),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_time"), data.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "The block must end after it starts.")
        if start and end and self.instance.pk is None:
            doctor = self.instance.doctor
            if doctor and doctor.availability.filter(weekday=data["weekday"], start_time__lt=end,
                                                     end_time__gt=start, active=True).exists():
                raise forms.ValidationError("That block overlaps an existing one.")
        return data


def build_doctor_form():
    from .models import Doctor

    class _DoctorProfileForm(forms.ModelForm):
        class Meta:
            model = Doctor
            fields = ["speciality", "bio", "fee", "slot_minutes", "room", "accepting_new"]
            widgets = {
                "speciality": forms.Select(attrs={"class": "form-control"}),
                "bio": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
                "fee": forms.NumberInput(attrs={"class": "form-control", "min": "0", "step": "0.01"}),
                "slot_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "10", "max": "120", "step": "5"}),
                "room": forms.TextInput(attrs={"class": "form-control"}),
            }

    return _DoctorProfileForm
