"""FitTrack models — exercises, logged workouts, personal bests, goals and streaks."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone


class Exercise(models.Model):
    class Unit(models.TextChoices):
        REPS = "reps", "Reps"
        TIME = "time", "Time"
        DISTANCE = "distance", "Distance"

    class Muscle(models.TextChoices):
        CHEST = "chest", "Chest"
        BACK = "back", "Back"
        LEGS = "legs", "Legs"
        SHOULDERS = "shoulders", "Shoulders"
        ARMS = "arms", "Arms"
        CORE = "core", "Core"
        CARDIO = "cardio", "Cardio"
        FULL_BODY = "full_body", "Full body"

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    muscle_group = models.CharField(max_length=10, choices=Muscle.choices)
    unit = models.CharField(max_length=8, choices=Unit.choices, default=Unit.REPS)
    description = models.CharField(max_length=240, blank=True)
    is_compound = models.BooleanField(default=False)

    class Meta:
        ordering = ["muscle_group", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("exercise_detail", kwargs={"slug": self.slug})

    def best_for(self, user):
        """This user's best set: heaviest weight, then greatest volume (Python-side,
        because volume is a computed property rather than a column)."""
        sets = list(WorkoutSet.objects.filter(workout__user=user, exercise=self))
        if not sets:
            return None
        return max(sets, key=lambda s: (s.weight_kg or 0, s.volume_kg))

    def history_for(self, user, limit=20):
        return (WorkoutSet.objects.filter(workout__user=user, exercise=self)
                .select_related("workout").order_by("-workout__date")[:limit])


class Workout(models.Model):
    class Feel(models.TextChoices):
        GREAT = "great", "Great"
        GOOD = "good", "Good"
        OK = "ok", "OK"
        TOUGH = "tough", "Tough"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workouts")
    title = models.CharField(max_length=100)
    date = models.DateField(default=timezone.localdate)
    duration_minutes = models.PositiveSmallIntegerField(default=45, validators=[MinValueValidator(1)])
    feel = models.CharField(max_length=5, choices=Feel.choices, default=Feel.GOOD)
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created"]
        constraints = [
            # One session per day per title keeps the log readable.
            models.UniqueConstraint(fields=["user", "date", "title"], name="one_session_per_title_per_day"),
        ]

    def __str__(self):
        return f"{self.title} · {self.date}"

    def get_absolute_url(self):
        return reverse("workout_detail", kwargs={"pk": self.pk})

    @property
    def total_volume(self) -> Decimal:
        return sum((s.volume_kg for s in self.sets.all()), Decimal("0"))

    @property
    def total_sets(self) -> int:
        return sum(s.sets for s in self.sets.all())

    @property
    def exercise_count(self) -> int:
        return self.sets.count()

    @property
    def pr_count(self) -> int:
        return self.sets.filter(is_personal_best=True).count()

    def add_set(self, exercise, sets, reps=0, weight_kg=None, duration_seconds=0, distance_km=None):
        """Log a set and auto-detect a personal best, atomically."""
        with transaction.atomic():
            entry = WorkoutSet.objects.create(
                workout=self, exercise=exercise, sets=sets, reps=reps,
                weight_kg=weight_kg, duration_seconds=duration_seconds,
                distance_km=distance_km, order=self.sets.count(),
            )
            entry.detect_personal_best()
        return entry


class WorkoutSet(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="sets")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="sets")
    sets = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    reps = models.PositiveSmallIntegerField(default=0)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                    validators=[MinValueValidator(0)])
    duration_seconds = models.PositiveIntegerField(default=0)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True,
                                      validators=[MinValueValidator(0)])
    is_personal_best = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.exercise.name} × {self.sets}"

    @property
    def volume_kg(self) -> Decimal:
        """Volume = sets × reps × weight (0 when the set isn't weighted)."""
        if not self.weight_kg:
            return Decimal("0")
        return Decimal(self.sets) * Decimal(self.reps) * Decimal(self.weight_kg)

    @property
    def distance_display(self):
        return f"{self.distance_km} km" if self.distance_km else ""

    def detect_personal_best(self) -> bool:
        """Flag this set if it beats every earlier set for the same exercise.

        Weighted work compares volume (sets × reps × weight); unweighted time
        and distance efforts compare duration/distance so cardio PRs count too.
        """
        previous = (WorkoutSet.objects.filter(workout__user=self.workout.user, exercise=self.exercise)
                    .exclude(pk=self.pk))
        best_weight = previous.order_by("-weight_kg").values_list("weight_kg", flat=True).first()
        best_volume = max((s.volume_kg for s in previous), default=Decimal("0"))
        best_duration = previous.order_by("-duration_seconds").values_list("duration_seconds", flat=True).first() or 0
        best_distance = previous.order_by("-distance_km").values_list("distance_km", flat=True).first() or Decimal("0")

        is_pr = False
        if self.weight_kg and (best_weight is None or self.weight_kg > best_weight):
            is_pr = True
        if self.volume_kg and self.volume_kg > best_volume and not previous.filter(
                weight_kg=self.weight_kg, reps=self.reps, sets=self.sets).exists():
            is_pr = is_pr or self.volume_kg > best_volume
        if not self.weight_kg and self.duration_seconds and self.duration_seconds > best_duration:
            is_pr = True
        if not self.weight_kg and self.distance_km and self.distance_km > best_distance:
            is_pr = True

        if is_pr != self.is_personal_best:
            self.is_personal_best = is_pr
            self.save(update_fields=["is_personal_best"])
        return is_pr


class Goal(models.Model):
    class Kind(models.TextChoices):
        WORKOUTS_PER_WEEK = "workouts_week", "Workouts per week"
        TOTAL_VOLUME = "volume", "Total volume this month (kg)"
        DISTANCE = "distance", "Distance this month (km)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals")
    kind = models.CharField(max_length=14, choices=Kind.choices)
    target = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind"]
        constraints = [
            models.UniqueConstraint(fields=["user", "kind"], condition=models.Q(active=True),
                                    name="one_active_goal_per_kind"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} → {self.target}"

    # ------------------------------------------------------------- progress
    def current_value(self) -> Decimal:
        today = timezone.localdate()
        if self.kind == self.Kind.WORKOUTS_PER_WEEK:
            start = today - timedelta(days=today.weekday())
            return Decimal(Workout.objects.filter(user=self.user, date__gte=start, date__lte=today).count())
        start = today.replace(day=1)
        sets = WorkoutSet.objects.filter(workout__user=self.user, workout__date__gte=start, workout__date__lte=today)
        if self.kind == self.Kind.TOTAL_VOLUME:
            return sum((s.volume_kg for s in sets), Decimal("0"))
        return sum((s.distance_km or Decimal("0") for s in sets), Decimal("0"))

    @property
    def progress_percent(self) -> int:
        if not self.target:
            return 0
        return min(100, round(100 * float(self.current_value()) / float(self.target)))

    @property
    def is_complete(self) -> bool:
        return self.current_value() >= self.target


class BodyWeight(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="weights")
    date = models.DateField(default=timezone.localdate)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(20)])

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="one_weight_per_day")]

    def __str__(self):
        return f"{self.date}: {self.weight_kg} kg"


def current_streak(user, today=None) -> int:
    """Consecutive days ending today (or yesterday) with at least one logged workout."""
    today = today or timezone.localdate()
    days = set(Workout.objects.filter(user=user, date__lte=today, date__gte=today - timedelta(days=365))
               .values_list("date", flat=True))
    if not days:
        return 0
    if today not in days and (today - timedelta(days=1)) not in days:
        return 0
    cursor = today if today in days else today - timedelta(days=1)
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def week_summary(user, today=None):
    """Counts for the calendar week containing `today` (Monday-based)."""
    today = today or timezone.localdate()
    start = today - timedelta(days=today.weekday())
    workouts = Workout.objects.filter(user=user, date__gte=start, date__lte=today)
    sets = WorkoutSet.objects.filter(workout__in=workouts)
    return {
        "start": start,
        "workouts": workouts.count(),
        "minutes": sum(w.duration_minutes for w in workouts),
        "volume": sum((s.volume_kg for s in sets), Decimal("0")),
        "sets": sum(s.sets for s in sets),
        "distance": sum((s.distance_km or Decimal("0") for s in sets), Decimal("0")),
        "prs": sets.filter(is_personal_best=True).count(),
    }
