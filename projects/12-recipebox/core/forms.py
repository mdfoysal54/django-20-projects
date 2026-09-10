"""RecipeBox forms."""
from django import forms

from .models import Collection, Rating, Recipe


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = ["title", "cuisine", "summary", "emoji", "prep_minutes", "cook_minutes",
                  "servings", "difficulty", "ingredients", "steps", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Chicken biryani"}),
            "cuisine": forms.Select(attrs={"class": "form-control"}),
            "summary": forms.TextInput(attrs={"class": "form-control", "placeholder": "One line that makes people hungry"}),
            "emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "prep_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "cook_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "servings": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "99"}),
            "difficulty": forms.Select(attrs={"class": "form-control"}),
            "ingredients": forms.Textarea(attrs={"class": "form-control", "rows": 9,
                                                 "placeholder": "200 g basmati rice\n1/2 tsp turmeric\n2 onions, sliced"}),
            "steps": forms.Textarea(attrs={"class": "form-control", "rows": 9,
                                           "placeholder": "One step per line."}),
        }

    def clean_ingredients(self):
        value = self.cleaned_data["ingredients"].strip()
        if len([l for l in value.splitlines() if l.strip()]) < 2:
            raise forms.ValidationError("Add at least two ingredients, one per line.")
        return value

    def clean_steps(self):
        value = self.cleaned_data["steps"].strip()
        if len([l for l in value.splitlines() if l.strip()]) < 2:
            raise forms.ValidationError("Add at least two steps, one per line.")
        return value


class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ["stars", "review"]
        widgets = {
            "stars": forms.Select(choices=[(i, f"{i} ★") for i in range(5, 0, -1)],
                                  attrs={"class": "form-control"}),
            "review": forms.TextInput(attrs={"class": "form-control",
                                             "placeholder": "How did it turn out? (optional)"}),
        }


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Weeknight dinners"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
        }
