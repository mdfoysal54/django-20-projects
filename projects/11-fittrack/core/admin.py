"""FitTrack — Django admin registrations."""
from django.contrib import admin

from .models import BodyWeight, Exercise, Goal, Workout, WorkoutSet


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["name", "muscle_group", "unit", "is_compound", "times_logged"]
    list_filter = ["muscle_group", "unit", "is_compound"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Logged")
    def times_logged(self, obj):
        return obj.sets.count()


class WorkoutSetInline(admin.TabularInline):
    model = WorkoutSet
    extra = 0
    fields = ["order", "exercise", "sets", "reps", "weight_kg", "duration_seconds", "distance_km", "is_personal_best"]
    readonly_fields = ["is_personal_best"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "date", "duration_minutes", "feel", "n_sets", "volume"]
    list_filter = ["feel", "date", "user"]
    search_fields = ["title", "notes", "user__username"]
    date_hierarchy = "date"
    inlines = [WorkoutSetInline]

    @admin.display(description="Sets")
    def n_sets(self, obj):
        return obj.total_sets

    @admin.display(description="Volume (kg)")
    def volume(self, obj):
        return obj.total_volume


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "target", "current", "active"]
    list_filter = ["kind", "active"]

    @admin.display(description="Current")
    def current(self, obj):
        return obj.current_value()


@admin.register(BodyWeight)
class BodyWeightAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "weight_kg"]
    list_filter = ["date"]
    search_fields = ["user__username"]
    date_hierarchy = "date"


@admin.register(WorkoutSet)
class WorkoutSetAdmin(admin.ModelAdmin):
    list_display = ["workout", "exercise", "sets", "reps", "weight_kg", "is_personal_best"]
    list_filter = ["exercise__muscle_group", "is_personal_best"]
    search_fields = ["workout__title", "exercise__name"]
