"""StayHub forms — search and booking with full date/capacity validation."""
from django import forms
from django.utils import timezone

from .models import Booking, Room


class SearchForm(forms.Form):
    city = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "City, e.g. Dhaka"}),
    )
    check_in = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    check_out = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    guests = forms.IntegerField(
        min_value=1, max_value=10, initial=2, required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 10}),
    )

    def clean(self):
        cleaned = super().clean()
        check_in, check_out = cleaned.get("check_in"), cleaned.get("check_out")
        today = timezone.localdate()
        if check_in and check_in < today:
            self.add_error("check_in", "Check-in cannot be in the past.")
        if check_in and check_out:
            if check_out <= check_in:
                self.add_error("check_out", "Check-out must be after check-in.")
            elif (check_out - check_in).days > Booking.MAX_NIGHTS:
                self.add_error("check_out", f"Maximum stay is {Booking.MAX_NIGHTS} nights.")
        return cleaned

    def ranges(self):
        """(check_in, check_out) or (None, None) when not searching by date."""
        return self.cleaned_data.get("check_in"), self.cleaned_data.get("check_out")


class BookingForm(forms.ModelForm):
    """Guest details. Dates/room arrive as hidden fields and are re-validated."""

    class Meta:
        model = Booking
        fields = ["guests", "special_requests"]
        widgets = {
            "guests": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 10}),
            "special_requests": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Late check-in, allergies, cot request…"}
            ),
        }

    def __init__(self, *args, room: Room, check_in, check_out, **kwargs):
        self.room = room
        self.check_in = check_in
        self.check_out = check_out
        super().__init__(*args, **kwargs)
        self.fields["guests"].initial = min(2, room.capacity)
        self.fields["guests"].max_value = room.capacity
        self.fields["guests"].widget.attrs["max"] = room.capacity

    def clean_guests(self):
        guests = self.cleaned_data["guests"]
        if guests > self.room.capacity:
            raise forms.ValidationError(
                f"Room {self.room.number} sleeps at most {self.room.capacity} guest(s)."
            )
        return guests

    def clean(self):
        cleaned = super().clean()
        today = timezone.localdate()
        if self.check_in < today:
            self.add_error(None, "Check-in cannot be in the past.")
        elif self.check_out <= self.check_in:
            self.add_error(None, "Check-out must be after check-in.")
        elif (self.check_out - self.check_in).days > Booking.MAX_NIGHTS:
            self.add_error(None, f"Maximum stay is {Booking.MAX_NIGHTS} nights.")
        elif not self.room.is_available(self.check_in, self.check_out):
            self.add_error(None, "That room is already booked for part of those dates.")
        return cleaned

    @property
    def nights(self) -> int:
        return max((self.check_out - self.check_in).days, 0)


class HotelFilterForm(forms.Form):
    """Room-count style filters used on the results page."""

    min_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(
        attrs={"class": "form-control", "placeholder": "Min $/night"}))
    max_price = forms.DecimalField(required=False, min_value=0, widget=forms.NumberInput(
        attrs={"class": "form-control", "placeholder": "Max $/night"}))
    stars = forms.ChoiceField(
        required=False,
        choices=[("", "Any rating")] + [(str(i), f"{i}★") for i in range(1, 6)],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

