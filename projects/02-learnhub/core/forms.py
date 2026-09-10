"""LearnHub forms — course & lesson authoring + enrolment-side validation."""
from django import forms

from .models import Course, Lesson


class CourseForm(forms.ModelForm):
    """Instructors create/edit their own courses. Status is never user-writable here."""

    class Meta:
        model = Course
        fields = ["title", "summary", "description", "level", "price"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Django for Beginners"}),
            "summary": forms.TextInput(attrs={"class": "form-control", "placeholder": "One-line pitch (max 240 chars)"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5,
                                                 "placeholder": "What will students learn? Prerequisites? Outcomes?"}),
            "level": forms.Select(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        }

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Give the course a descriptive title (min 5 characters).")
        return title

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is not None and price > 9999:
            raise forms.ValidationError("Price looks unrealistic — contact support for premium tiers.")
        return price


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "order", "duration_minutes", "resource_url", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "resource_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https:// (optional)"}),
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
        }

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("order")
        course = self.instance.course if self.instance.pk else self.course
        if order and course:
            clash = Lesson.objects.filter(course=course, order=order)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                self.add_error("order", "Another lesson already uses this position.")
        return cleaned

    def __init__(self, *args, course=None, **kwargs):
        self.course = course
        super().__init__(*args, **kwargs)
