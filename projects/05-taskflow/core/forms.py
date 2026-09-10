"""TaskFlow forms — projects, membership, tasks and comments."""
from django import forms
from django.contrib.auth.models import User

from .models import Comment, Membership, Project, Task


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Website Redesign"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "color": forms.TextInput(attrs={"class": "form-control", "type": "color", "style": "height:44px"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 3:
            raise forms.ValidationError("Project names need at least 3 characters.")
        return name


class MemberAddForm(forms.Form):
    """Add an existing platform user to a project by username."""

    username = forms.CharField(max_length=150, widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "exact username"}))
    role = forms.ChoiceField(choices=Membership.Role.choices, initial=Membership.Role.MEMBER,
                             widget=forms.Select(attrs={"class": "form-control"}))

    def __init__(self, *args, project: Project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No user with that username exists.")
        if user == self.project.owner:
            raise forms.ValidationError("That user owns this project already.")
        if Membership.objects.filter(project=self.project, user=user).exists():
            raise forms.ValidationError("That user is already a member.")
        self.user = user
        return user.username


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "status", "priority", "assignee", "due_date", "estimate_hours"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "What needs to be done?"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "status": forms.Select(attrs={"class": "form-control"}),
            "priority": forms.Select(attrs={"class": "form-control"}),
            "assignee": forms.Select(attrs={"class": "form-control"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "estimate_hours": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 500}),
        }

    def __init__(self, *args, project: Project, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        # Assignees are limited to project participants (owner + members).
        member_ids = list(project.memberships.values_list("user_id", flat=True))
        member_ids.append(project.owner_id)
        self.fields["assignee"].queryset = User.objects.filter(pk__in=member_ids).order_by("username")
        self.fields["assignee"].empty_label = "Unassigned"
        self.fields["assignee"].required = False

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 3:
            raise forms.ValidationError("Give the task a clear title (min 3 characters).")
        return title

    def clean_assignee(self):
        assignee = self.cleaned_data.get("assignee")
        if assignee is not None:
            allowed = self.project.memberships.filter(user=assignee).exists() or assignee.pk == self.project.owner_id
            if not allowed:
                raise forms.ValidationError("You can only assign tasks to project members.")
        return assignee


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                          "placeholder": "Write a comment…"}),
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 2:
            raise forms.ValidationError("Say a little more than that.")
        return body
