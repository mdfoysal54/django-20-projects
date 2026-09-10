"""HelpDesk forms."""
from django import forms
from django.contrib.auth.models import User

from .models import Department, Feedback, Ticket, TicketMessage


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "department", "priority", "body"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief summary of the issue"}),
            "department": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 8,
                                          "placeholder": "What happened? What did you expect? What have you tried?"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Customers don't get to self-declare "urgent" — agents do that on triage.
        self.fields["priority"].choices = [c for c in Ticket.Priority.choices if c[0] != Ticket.Priority.URGENT]
        if user is not None and not user.is_staff:
            self.fields["priority"].initial = Ticket.Priority.NORMAL

    def clean_subject(self):
        subject = self.cleaned_data["subject"].strip()
        if len(subject) < 8:
            raise forms.ValidationError("Give the subject at least 8 characters so agents can triage it.")
        return subject

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 20:
            raise forms.ValidationError("Please describe the problem in a little more detail (20+ characters).")
        return body


class ReplyForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["body", "internal"]
        widgets = {
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Write a reply…"}),
        }

    def __init__(self, *args, staff=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not staff:
            # Customers can never post internal notes — the field is not rendered.
            self.fields.pop("internal", None)

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 2:
            raise forms.ValidationError("Write a message first.")
        return body


class TriageForm(forms.Form):
    """Agent-only: change priority, status and assignment in one shot."""

    priority = forms.ChoiceField(choices=Ticket.Priority.choices, widget=forms.Select(attrs={"class": "form-control"}))
    status = forms.ChoiceField(choices=Ticket.Status.choices, widget=forms.Select(attrs={"class": "form-control"}))
    assignee = forms.ModelChoiceField(queryset=User.objects.none(), required=False,
                                      widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, ticket=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket = ticket
        self.fields["assignee"].queryset = User.objects.filter(is_staff=True, is_active=True).order_by("username")
        self.fields["assignee"].label = "Assignee"
        self.fields["assignee"].empty_label = "— unassigned —"
        if ticket:
            self.fields["priority"].initial = ticket.priority
            self.fields["status"].initial = ticket.status
            self.fields["assignee"].initial = ticket.assignee_id
            # Only offer legal next states (plus the current one).
            allowed = Ticket.ALLOWED_TRANSITIONS.get(ticket.status, set()) | {ticket.status}
            self.fields["status"].choices = [(v, l) for v, l in Ticket.Status.choices if v in allowed]


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "slug", "emoji", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
        }


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["score", "comment"]
        widgets = {
            "score": forms.Select(choices=[(i, f"{i} — {'★' * i}") for i in range(1, 6)],
                                  attrs={"class": "form-control"}),
            "comment": forms.TextInput(attrs={"class": "form-control", "placeholder": "Anything else? (optional)"}),
        }
