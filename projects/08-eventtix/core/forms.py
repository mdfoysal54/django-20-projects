"""EventTix forms."""
from django import forms
from django.core.validators import MinValueValidator
from django.db.models import F

from .models import Event, TicketTier


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "venue", "starts_at", "ends_at", "cover_emoji", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dhaka Sound Festival"}),
            "venue": forms.TextInput(attrs={"class": "form-control", "placeholder": "Bangabandhu Arena"}),
            "starts_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"},
                                             format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"},
                                           format="%Y-%m-%dT%H:%M"),
            "cover_emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("starts_at", "ends_at"):
            self.fields[f].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        self.fields["ends_at"].required = False

    def clean(self):
        data = super().clean()
        starts, ends = data.get("starts_at"), data.get("ends_at")
        if starts and ends and ends <= starts:
            self.add_error("ends_at", "The event must end after it starts.")
        return data


class TierForm(forms.ModelForm):
    class Meta:
        model = TicketTier
        fields = ["name", "price", "capacity", "order"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "General / VIP / Early bird"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

    def clean_capacity(self):
        capacity = self.cleaned_data["capacity"]
        if self.instance.pk and capacity < self.instance.sold:
            raise forms.ValidationError(
                f"{self.instance.sold} tickets are already sold — capacity cannot drop below that."
            )
        return capacity


class BookingForm(forms.Form):
    tier = forms.ModelChoiceField(queryset=TicketTier.objects.none(), widget=forms.HiddenInput)
    quantity = forms.IntegerField(min_value=1, max_value=10,
                                  validators=[MinValueValidator(1)],
                                  widget=forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "10"}))

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Only tiers with seats left are bookable.
        self.fields["tier"].queryset = (event.tiers.filter(sold__lt=F("capacity"))
                                        if event else TicketTier.objects.none())


class CheckInForm(forms.Form):
    reference = forms.CharField(max_length=16, widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "ET-XXXXXXXX", "autofocus": True}))
