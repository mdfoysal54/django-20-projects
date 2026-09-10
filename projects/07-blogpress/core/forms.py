"""BlogPress forms."""
from django import forms

from .models import Comment, Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "category", "excerpt", "body", "cover_emoji", "featured"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "A headline worth clicking"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "excerpt": forms.TextInput(attrs={"class": "form-control", "placeholder": "One-line teaser (optional)"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 12,
                                          "placeholder": "Write your post… plain text, blank line = new paragraph"}),
            "cover_emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Titles need at least 5 characters.")
        return title

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 50:
            raise forms.ValidationError("Posts need a real body — at least 50 characters.")
        return body


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                          "placeholder": "Add to the discussion…"}),
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if len(body) < 3:
            raise forms.ValidationError("That's a bit short.")
        return body
