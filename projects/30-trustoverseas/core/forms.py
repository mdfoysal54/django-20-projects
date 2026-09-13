"""Trust Overseas Ltd — domain forms."""
from django import forms
from django.contrib.auth.models import User

from .models import (
    Attestation, Client, Invoice, Lead, Leave, Passport, PettyCash, PortalSubmission,
    Staff, SubAgent, VisaCase,
)


def _style(form):
    for field in form.fields.values():
        existing = field.widget.attrs.get("class", "")
        if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect, forms.FileInput)):
            field.widget.attrs["class"] = (existing + " form-control").strip()
        if isinstance(field.widget, forms.DateInput) and not field.widget.attrs.get("type"):
            field.widget.input_type = "date"
            field.widget.attrs.setdefault("type", "date")
    return form


class StyledModelForm(forms.ModelForm):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class LeadForm(StyledModelForm):
    class Meta:
        model = Lead
        fields = ("name", "phone", "destination", "visa_category", "source", "note")


class ClientForm(StyledModelForm):
    class Meta:
        model = Client
        fields = (
            "first_name", "last_name", "father_name", "mother_name", "gender", "dob",
            "nationality", "phone", "whatsapp", "email", "district", "address",
            "education", "trade", "experience_years", "source", "agent", "desk", "kyc",
        )
        widgets = {"dob": forms.DateInput(attrs={"type": "date"})}


class PassportForm(StyledModelForm):
    class Meta:
        model = Passport
        fields = (
            "client", "number", "issuing_country", "issue_date", "expiry_date",
            "place_of_issue", "blank_pages", "location", "envelope",
        )
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
        }


class CaseOpenForm(forms.Form):
    client = forms.ModelChoiceField(queryset=Client.objects.all())
    passport = forms.ModelChoiceField(queryset=Passport.objects.all())
    destination = forms.ChoiceField(choices=[
        ("SAU", "Saudi Arabia"), ("ARE", "UAE"), ("QAT", "Qatar"),
        ("KWT", "Kuwait"), ("BHR", "Bahrain"), ("OMN", "Oman"),
        ("MYS", "Malaysia"), ("SGP", "Singapore"), ("OTHER", "Other"),
    ])
    visa_category = forms.ChoiceField(choices=[
        ("Work", "Work / employment"), ("Visit", "Visit"),
        ("Umrah", "Umrah"), ("Family", "Family / dependent"),
        ("Student", "Student"),
    ])
    job_title = forms.CharField(required=False)
    agent = forms.ModelChoiceField(queryset=SubAgent.objects.all(), required=False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class InvoiceForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    tax = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    discount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    description = forms.CharField(initial="Visa package")
    due_days = forms.IntegerField(initial=15, min_value=0)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class ReceiptForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    method = forms.ChoiceField(choices=[
        ("cash", "Cash"), ("bank", "Bank"), ("bkash", "bKash"),
        ("nagad", "Nagad"), ("card", "Card"),
    ])
    reference = forms.CharField(required=False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class MedicalForm(forms.Form):
    result = forms.ChoiceField(choices=[
        ("sched", "Scheduled"), ("fit", "Fit"), ("unfit", "Unfit"), ("held", "Held"),
    ])
    clinic = forms.CharField(required=False)
    slip = forms.CharField(required=False, label="GAMCA / Wafid slip")
    issued_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class AttestationForm(StyledModelForm):
    class Meta:
        model = Attestation
        fields = ("certificate", "authority", "order", "consignment", "gov_fee", "service_fee")


class PortalForm(StyledModelForm):
    class Meta:
        model = PortalSubmission
        fields = ("portal", "application_no", "sponsor", "status_raw")


class PettyForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    purpose = forms.CharField(max_length=200)
    expense_code = forms.ChoiceField(choices=[
        ("5020", "Wafid / medical"), ("5010", "Embassy / consular"),
        ("5030", "Courier & apostille"), ("6020", "Rent & utilities"),
        ("6010", "Staff salaries"),
    ])

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class LeaveForm(StyledModelForm):
    class Meta:
        model = Leave
        fields = ("kind", "start", "end", "reason")
        widgets = {
            "start": forms.DateInput(attrs={"type": "date"}),
            "end": forms.DateInput(attrs={"type": "date"}),
        }


class AgentForm(StyledModelForm):
    class Meta:
        model = SubAgent
        fields = ("name", "contact", "phone", "email", "district",
                  "credit_limit", "commission_value", "commission_model")


class TrackForm(forms.Form):
    number = forms.CharField(label="File number")
    pin = forms.CharField(label="Tracking PIN", max_length=6)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class DocumentForm(forms.Form):
    kind = forms.CharField(max_length=40)
    filename = forms.CharField(max_length=160, required=False)
    note = forms.CharField(max_length=200, required=False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class CustodyForm(forms.Form):
    to_loc = forms.ChoiceField(choices=Passport.Loc.choices)
    note = forms.CharField(required=False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)


class PayrollForm(forms.Form):
    period = forms.CharField(max_length=7, help_text="YYYY-MM")
    housing = forms.DecimalField(required=False, initial=0)
    transport = forms.DecimalField(required=False, initial=0)
    bonus = forms.DecimalField(required=False, initial=0)
    commission = forms.DecimalField(required=False, initial=0)
    deductions = forms.DecimalField(required=False, initial=0)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        _style(self)
