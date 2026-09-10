"""ShopNest forms — every mutation goes through a validated Django form."""
from django import forms

from .models import Order


class AddToCartForm(forms.Form):
    """Bounded by the product stock in the view (max_per_order)."""

    quantity = forms.IntegerField(
        min_value=1,
        max_value=99,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 99}),
    )


class CartQuantityForm(forms.Form):
    """Re-validates the requested quantity per line; 0 deletes the line."""

    quantity = forms.IntegerField(min_value=0, max_value=99)


class CheckoutForm(forms.ModelForm):
    """Shipping details for a new order. Every field is user-typed → cleaned."""

    class Meta:
        model = Order
        fields = ["shipping_address", "city", "phone"]
        widgets = {
            "shipping_address": forms.Textarea(
                attrs={"rows": 3, "class": "form-control", "placeholder": "House, road, area…"}
            ),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "Dhaka"}),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+8801XXXXXXXXX", "autocomplete": "tel"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.label_suffix = ""

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if not (7 <= len(digits) <= 15):
            raise forms.ValidationError("Enter a valid phone number (7–15 digits).")
        return phone
