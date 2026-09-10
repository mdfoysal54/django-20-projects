"""LinkShort forms."""
from django import forms
from django.core.exceptions import ValidationError

from .models import ShortLink, normalise_target


class LinkForm(forms.ModelForm):
    class Meta:
        model = ShortLink
        fields = ["target_url", "title", "tags", "expires_at", "max_clicks", "active"]
        widgets = {
            "target_url": forms.URLInput(attrs={"class": "form-control",
                                                "placeholder": "https://example.com/a/long/path?with=params"}),
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Launch announcement"}),
            "tags": forms.TextInput(attrs={"class": "form-control", "placeholder": "marketing, q3"}),
            "expires_at": forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"},
                                              format="%Y-%m-%dT%H:%M"),
            "max_clicks": forms.NumberInput(attrs={"class": "form-control", "placeholder": "No limit"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expires_at"].required = False
        self.fields["expires_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"]
        self.fields["max_clicks"].required = False
        self.fields["tags"].required = False
        self.fields["max_clicks"].widget.attrs["min"] = 1     # model default of 0 would allow a dead link

    def clean_target_url(self):
        raw = self.cleaned_data["target_url"]
        try:
            value = normalise_target(raw)
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
        return value

    def clean(self):
        data = super().clean()
        target, expires = data.get("target_url"), data.get("expires_at")
        if expires and expires <= __import__("django.utils.timezone", fromlist=["timezone"]).now():
            self.add_error("expires_at", "The expiry must be in the future.")
        max_clicks = data.get("max_clicks")
        if max_clicks is not None and max_clicks < 1:
            self.add_error("max_clicks", "Use at least 1, or leave blank for unlimited.")
        # Refuse to shorten our own domain — that would create a redirect loop.
        if target:
            from django.conf import settings
            host = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(target).netloc.split(":")[0].lower()
            for allowed in getattr(settings, "ALLOWED_HOSTS", []):
                if allowed and allowed != "*" and host == allowed.lower():
                    self.add_error("target_url", "That link points back at LinkShort itself.")
                    break
        return data


class QuickShortenForm(forms.Form):
    """The one-field form on the dashboard: paste a URL, get a short link."""

    target_url = forms.CharField(max_length=500, widget=forms.URLInput(
        attrs={"class": "form-control", "placeholder": "https://…", "autocomplete": "off"}))

    def clean_target_url(self):
        try:
            return normalise_target(self.cleaned_data["target_url"])
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages)
