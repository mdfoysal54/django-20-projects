"""DevJobs forms — employer posting/editing and candidate applications.

Resume uploads are hardened: extension allow-list, 2 MB size cap and filename
sanitisation happen server-side (the file input's `accept` attribute is UX only).
"""
from pathlib import Path

from django import forms

from .models import Application, Company, Job

ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"}
MAX_RESUME_BYTES = 2 * 1024 * 1024  # 2 MB


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "title", "description", "requirements", "location", "remote", "job_type",
            "level", "salary_min", "salary_max", "salary_currency", "tags", "deadline",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Senior Django Engineer"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "requirements": forms.Textarea(attrs={"class": "form-control", "rows": 5,
                                                  "placeholder": "One requirement per line"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "City, Country"}),
            "remote": forms.Select(attrs={"class": "form-control"}),
            "job_type": forms.Select(attrs={"class": "form-control"}),
            "level": forms.Select(attrs={"class": "form-control"}),
            "salary_min": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "100"}),
            "salary_max": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "100"}),
            "salary_currency": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "tags": forms.TextInput(attrs={"class": "form-control", "placeholder": "Django, PostgreSQL, Docker"}),
            "deadline": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Give the role a descriptive title (min 5 characters).")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 60:
            raise forms.ValidationError("Write at least a few sentences (60+ characters) so candidates know what to expect.")
        return description

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("salary_min"), cleaned.get("salary_max")
        if low is not None and high is not None and low > high:
            self.add_error("salary_max", "Maximum salary must be greater than or equal to the minimum.")
        return cleaned


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["name", "website", "location", "about", "logo_emoji"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Acme Ltd."}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "HQ city"}),
            "about": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "logo_emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
        }


class ApplicationForm(forms.ModelForm):
    """Candidates apply with a cover letter + optional resume/portfolio."""

    class Meta:
        model = Application
        fields = ["cover_letter", "resume", "portfolio_url"]
        widgets = {
            "cover_letter": forms.Textarea(attrs={
                "class": "form-control", "rows": 6,
                "placeholder": "Why are you a great fit? Keep it specific and kind.",
            }),
            "resume": forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdf,.doc,.docx,.txt,.rtf,.odt"}),
            "portfolio_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://github.com/you (optional)"}),
        }

    def clean_cover_letter(self):
        letter = self.cleaned_data["cover_letter"].strip()
        if len(letter) < 40:
            raise forms.ValidationError("Tell the employer a bit more — at least 40 characters.")
        return letter

    def clean_resume(self):
        upload = self.cleaned_data.get("resume")
        if not upload:
            return upload
        suffix = Path(upload.name).suffix.lower()
        if suffix not in ALLOWED_RESUME_EXTENSIONS:
            raise forms.ValidationError(
                "Unsupported file type. Upload one of: " + ", ".join(sorted(ALLOWED_RESUME_EXTENSIONS))
            )
        if upload.size > MAX_RESUME_BYTES:
            raise forms.ValidationError("Resume must be 2 MB or smaller.")
        # Strip any path components a malicious client tried to smuggle in.
        upload.name = Path(upload.name).name
        return upload


class ApplicationStatusForm(forms.ModelForm):
    """Employers move candidates through the pipeline + private notes."""

    class Meta:
        model = Application
        fields = ["status", "employer_notes"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
            "employer_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                                    "placeholder": "Private notes (candidate never sees these)"}),
        }
