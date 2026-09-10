"""FitTrack forms."""
from django import forms

from .models import BodyWeight, Exercise, Goal, Workout, WorkoutSet


class WorkoutForm(forms.ModelForm):
    class Meta:
        model = Workout
        fields = ["title", "date", "duration_minutes", "feel", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Push day A"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "duration_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "480"}),
            "feel": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 4,
                                           "placeholder": "How it went, what to change next time…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]

    def clean_date(self):
        from django.utils import timezone
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError("You cannot log a workout in the future.")
        return value


class SetForm(forms.Form):
    exercise = forms.ModelChoiceField(queryset=Exercise.objects.all(),
                                      widget=forms.Select(attrs={"class": "form-control"}))
    sets = forms.IntegerField(min_value=1, max_value=50, initial=3,
                              widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}))
    reps = forms.IntegerField(min_value=0, max_value=200, initial=8, required=False,
                              widget=forms.NumberInput(attrs={"class": "form-control", "min": "0"}))
    weight_kg = forms.DecimalField(min_value=0, max_value=500, required=False, decimal_places=2,
                                   widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}))
    duration_seconds = forms.IntegerField(min_value=0, max_value=36000, required=False, initial=0,
                                          widget=forms.NumberInput(attrs={"class": "form-control"}))
    distance_km = forms.DecimalField(min_value=0, max_value=500, required=False, decimal_places=2,
                                     widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}))

    def clean(self):
        data = super().clean()
        if data.get("sets") and not any([data.get("reps"), data.get("duration_seconds"), data.get("distance_km")]):
            raise forms.ValidationError("Enter reps, a duration or a distance — otherwise there is nothing to log.")
        return data

    def save(self, workout):
        data = self.cleaned_data
        return workout.add_set(
            exercise=data["exercise"], sets=data["sets"], reps=data["reps"] or 0,
            weight_kg=data["weight_kg"], duration_seconds=data["duration_seconds"] or 0,
            distance_km=data["distance_km"],
        )


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["kind", "target"]
        widgets = {
            "kind": forms.Select(attrs={"class": "form-control"}),
            "target": forms.NumberInput(attrs={"class": "form-control", "min": "1", "step": "0.5"}),
        }


class BodyWeightForm(forms.ModelForm):
    class Meta:
        model = BodyWeight
        fields = ["date", "weight_kg"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "weight_kg": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "20"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]

    def clean_date(self):
        from django.utils import timezone
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError("That date is in the future.")
        return value


class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ["name", "muscle_group", "unit", "is_compound", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "muscle_group": forms.Select(attrs={"class": "form-control"}),
            "unit": forms.Select(attrs={"class": "form-control"}),
            "description": forms.TextInput(attrs={"class": "form-control"}),
        }
