"""FitTrack views — dashboard, workout log, exercise progress, goals and body weight."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BodyWeightForm, ExerciseForm, GoalForm, SetForm, WorkoutForm
from .models import BodyWeight, Exercise, Goal, Workout, WorkoutSet, current_streak, week_summary


def index(request):
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, "fitness/index.html", {
        "exercise_count": Exercise.objects.count(),
        "workouts_logged": Workout.objects.count(),
        "total_volume": sum((s.volume_kg for s in WorkoutSet.objects.all()), 0),
    })


@login_required
def dashboard(request):
    today = timezone.localdate()
    summary = week_summary(request.user, today)
    recent = (Workout.objects.filter(user=request.user)
              .prefetch_related("sets__exercise")[:5])
    prs = (WorkoutSet.objects.filter(workout__user=request.user, is_personal_best=True)
           .select_related("exercise", "workout").order_by("-workout__date")[:6])
    goals = request.user.goals.filter(active=True)
    # 14-day activity strip for the little heatmap.
    days = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        count = Workout.objects.filter(user=request.user, date=day).count()
        days.append({"date": day, "count": count})
    weights = list(request.user.weights.order_by("-date")[:14])
    return render(request, "fitness/dashboard.html", {
        "summary": summary, "recent": recent, "prs": prs, "goals": goals,
        "streak": current_streak(request.user), "days": days,
        "weights": list(reversed(weights)),
        "weight_form": BodyWeightForm(initial={"date": today}),
        "total_workouts": Workout.objects.filter(user=request.user).count(),
    })


@login_required
def workout_list(request):
    workouts = Workout.objects.filter(user=request.user).annotate(n_sets=Count("sets"))
    q = request.GET.get("q", "").strip()
    if q:
        workouts = workouts.filter(Q(title__icontains=q) | Q(notes__icontains=q))
    paginator = Paginator(workouts, 10)
    return render(request, "fitness/workout_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q,
    })


@login_required
def workout_create(request):
    if request.method == "POST":
        form = WorkoutForm(request.POST)
        if form.is_valid():
            workout = form.save(commit=False)
            workout.user = request.user
            workout.save()
            messages.success(request, "Workout started — add your sets below.")
            return redirect(workout)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = WorkoutForm(initial={"date": timezone.localdate()})
    return render(request, "fitness/workout_form.html", {"form": form, "mode": "create"})


@login_required
def workout_edit(request, pk):
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    if request.method == "POST":
        form = WorkoutForm(request.POST, instance=workout)
        if form.is_valid():
            form.save()
            messages.success(request, "Workout updated.")
            return redirect(workout)
    else:
        form = WorkoutForm(instance=workout)
    return render(request, "fitness/workout_form.html", {"form": form, "workout": workout, "mode": "edit"})


@login_required
def workout_detail(request, pk):
    workout = get_object_or_404(Workout.objects.prefetch_related("sets__exercise"), pk=pk, user=request.user)
    return render(request, "fitness/workout_detail.html", {
        "workout": workout,
        "set_form": SetForm(initial={"exercise": request.GET.get("exercise") or None}),
    })


@login_required
@require_POST
def add_set(request, pk):
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    form = SetForm(request.POST)
    if form.is_valid():
        entry = form.save(workout)
        if entry.is_personal_best:
            messages.success(request, f"🏆 New personal best on {entry.exercise.name}!")
        else:
            messages.success(request, f"Logged {entry.exercise.name}.")
    else:
        messages.error(request, "Could not log that set — check the numbers.")
    return redirect(workout)


@login_required
@require_POST
def delete_set(request, pk):
    entry = get_object_or_404(WorkoutSet, pk=pk, workout__user=request.user)
    workout = entry.workout
    entry.delete()
    messages.success(request, "Set removed.")
    return redirect(workout)


@login_required
@require_POST
def delete_workout(request, pk):
    workout = get_object_or_404(Workout, pk=pk, user=request.user)
    workout.delete()
    messages.success(request, "Workout deleted.")
    return redirect("workout_list")


# ------------------------------------------------------------------ exercises
def exercise_list(request):
    exercises = Exercise.objects.all()
    muscle = request.GET.get("muscle", "")
    q = request.GET.get("q", "").strip()
    if muscle:
        exercises = exercises.filter(muscle_group=muscle)
    if q:
        exercises = exercises.filter(Q(name__icontains=q) | Q(description__icontains=q))
    return render(request, "fitness/exercise_list.html", {
        "exercises": exercises, "muscle": muscle, "q": q, "muscles": Exercise.Muscle.choices,
    })


def exercise_detail(request, slug):
    exercise = get_object_or_404(Exercise, slug=slug)
    history = []
    best = None
    if request.user.is_authenticated:
        history = exercise.history_for(request.user)
        best = exercise.best_for(request.user)
    chart = [{"date": h.workout.date, "value": float(h.weight_kg or h.volume_kg or h.distance_km or 0)}
             for h in reversed(history)]
    max_value = max([c["value"] for c in chart], default=0) or 1
    return render(request, "fitness/exercise_detail.html", {
        "exercise": exercise, "history": history, "best": best,
        "chart": chart, "max_value": max_value,
        "recent_users": (WorkoutSet.objects.filter(exercise=exercise).values("workout__user__username")
                         .annotate(n=Count("id")).order_by("-n")[:5]),
    })


@login_required
def exercise_create(request):
    if request.method == "POST":
        form = ExerciseForm(request.POST)
        if form.is_valid():
            exercise = form.save()
            messages.success(request, f"{exercise.name} added to the library.")
            return redirect(exercise)
    else:
        form = ExerciseForm()
    return render(request, "fitness/exercise_form.html", {"form": form})


# ---------------------------------------------------------------------- goals
@login_required
def goals(request):
    form = GoalForm()
    if request.method == "POST":
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            # One active goal per kind: replace rather than duplicate.
            Goal.objects.filter(user=request.user, kind=goal.kind, active=True).update(active=False)
            goal.save()
            messages.success(request, "Goal saved — progress updates as you log workouts.")
            return redirect("goals")
        messages.error(request, "Give the goal a target number.")
    all_goals = request.user.goals.all()
    return render(request, "fitness/goals.html", {
        "form": form,
        "active_goals": [g for g in all_goals if g.active],
        "past_goals": [g for g in all_goals if not g.active],
    })


@login_required
@require_POST
def goal_close(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    goal.active = False
    goal.save(update_fields=["active"])
    messages.success(request, "Goal retired.")
    return redirect("goals")


# ---------------------------------------------------------------- body weight
@login_required
@require_POST
def log_weight(request):
    form = BodyWeightForm(request.POST)
    if form.is_valid():
        entry, created = BodyWeight.objects.update_or_create(
            user=request.user, date=form.cleaned_data["date"],
            defaults={"weight_kg": form.cleaned_data["weight_kg"]},
        )
        messages.success(request, f"Weight logged for {entry.date}." if created else "Weight updated.")
    else:
        messages.error(request, "Enter a weight between 20 and 500 kg.")
    return redirect("dashboard" if request.POST.get("next") == "dashboard" else "bodyweight")


@login_required
def bodyweight(request):
    entries = list(request.user.weights.order_by("date"))
    change = None
    if len(entries) >= 2:
        change = entries[-1].weight_kg - entries[0].weight_kg
    chart_max = max([float(e.weight_kg) for e in entries], default=100) * 1.05
    chart_min = min([float(e.weight_kg) for e in entries], default=60) * 0.95
    return render(request, "fitness/bodyweight.html", {
        "entries": list(reversed(entries)), "change": change,
        "form": BodyWeightForm(initial={"date": timezone.localdate()}),
        "chart": [{"date": e.date, "value": float(e.weight_kg)} for e in entries],
        "chart_max": chart_max, "chart_min": chart_min,
    })


@login_required
def profile(request):
    return render(request, "account/profile.html", {
        "workouts": Workout.objects.filter(user=request.user).count(),
        "prs": WorkoutSet.objects.filter(workout__user=request.user, is_personal_best=True).count(),
        "streak": current_streak(request.user),
        "sets": WorkoutSet.objects.filter(workout__user=request.user).aggregate(n=Sum("sets"))["n"] or 0,
    })
