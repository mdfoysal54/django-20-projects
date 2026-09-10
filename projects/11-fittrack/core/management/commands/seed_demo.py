"""Seed FitTrack with an exercise library, two weeks of workouts, goals and weights."""
import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import BodyWeight, Exercise, Goal, Workout, WorkoutSet

EXERCISES = [
    ("Bench Press", "chest", "reps", True, "Barbell, shoulder-width grip, bar to mid-chest."),
    ("Incline Dumbbell Press", "chest", "reps", False, "30–45° bench, controlled tempo."),
    ("Pull-Up", "back", "reps", True, "Full hang to chin over bar."),
    ("Barbell Row", "back", "reps", True, "Hinge to 45°, pull to lower ribs."),
    ("Lat Pulldown", "back", "reps", False, "Wide grip, drive elbows down."),
    ("Back Squat", "legs", "reps", True, "Hip crease below parallel, braced core."),
    ("Romanian Deadlift", "legs", "reps", True, "Hinge at hips, feel the hamstrings."),
    ("Leg Press", "legs", "reps", False, "Feet shoulder width, controlled descent."),
    ("Overhead Press", "shoulders", "reps", True, "Strict press, no leg drive."),
    ("Lateral Raise", "shoulders", "reps", False, "Lead with the elbows, no swinging."),
    ("Barbell Curl", "arms", "reps", False, "Elbows pinned to the ribs."),
    ("Triceps Rope Pushdown", "arms", "reps", False, "Elbows fixed, full extension."),
    ("Plank", "core", "time", False, "Straight line, glutes engaged."),
    ("Hanging Leg Raise", "core", "reps", False, "No swinging — control the descent."),
    ("Running", "cardio", "distance", False, "Steady pace, conversational effort."),
    ("Rowing Machine", "cardio", "distance", False, "Legs → hips → arms sequence."),
    ("Kettlebell Swing", "full_body", "reps", True, "Hinge and snap, hips do the work."),
]

SESSIONS = [
    ("Push day — heavy", ["Bench Press", "Overhead Press", "Incline Dumbbell Press", "Triceps Rope Pushdown"]),
    ("Pull day — volume", ["Pull-Up", "Barbell Row", "Lat Pulldown", "Barbell Curl"]),
    ("Leg day", ["Back Squat", "Romanian Deadlift", "Leg Press", "Hanging Leg Raise"]),
    ("Conditioning", ["Running", "Rowing Machine", "Kettlebell Swing"]),
    ("Upper — accessory", ["Incline Dumbbell Press", "Lateral Raise", "Barbell Curl", "Plank"]),
]


class Command(BaseCommand):
    help = "Create demo exercises, workouts, goals and body-weight entries."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        rng = random.Random(20260910)

        for username, staff, first in [("coach", False, "Imran"), ("nadia", False, "Nadia"), ("admin", True, "Admin")]:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"first_name": first,
                                                                 "email": f"{username}@fittrack.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = user.is_superuser = True
            user.save()

        for name, muscle, unit, compound, description in EXERCISES:
            Exercise.objects.get_or_create(name=name, defaults={"muscle_group": muscle, "unit": unit,
                                                                "is_compound": compound,
                                                                "description": description})

        lifters = [User.objects.get(username=u) for u in ("coach", "nadia")]
        today = timezone.localdate()
        for lifter in lifters:
            base = {  # per-lifter baseline weights so PRs are meaningful
                "Bench Press": Decimal("70.00"), "Back Squat": Decimal("100.00"),
                "Romanian Deadlift": Decimal("90.00"), "Overhead Press": Decimal("45.00"),
                "Barbell Row": Decimal("65.00"), "Lat Pulldown": Decimal("55.00"),
                "Leg Press": Decimal("140.00"), "Incline Dumbbell Press": Decimal("26.00"),
                "Lateral Raise": Decimal("10.00"), "Barbell Curl": Decimal("30.00"),
                "Triceps Rope Pushdown": Decimal("25.00"), "Kettlebell Swing": Decimal("24.00"),
            }
            if lifter.username == "nadia":
                base = {k: (v * Decimal("0.72")).quantize(Decimal("0.5")) for k, v in base.items()}

            for day_offset in range(0, 21):
                if day_offset % 7 == 3 or day_offset % 7 == 6:
                    continue                       # rest days keep the streak realistic
                title, exercises = SESSIONS[day_offset % len(SESSIONS)]
                date = today - timedelta(days=day_offset)
                workout, created = Workout.objects.get_or_create(
                    user=lifter, title=title, date=date,
                    defaults={"duration_minutes": rng.choice([45, 55, 60, 70, 80]),
                              "feel": rng.choice(["great", "good", "ok", "tough"]),
                              "notes": "Felt strong on the top sets." if day_offset % 3 == 0 else ""},
                )
                if not created:
                    continue
                progress = Decimal(1) + Decimal(day_offset and (21 - day_offset)) / Decimal(200)
                for ex_name in exercises:
                    exercise = Exercise.objects.get(name=ex_name)
                    if exercise.unit == "distance":
                        workout.add_set(exercise, sets=1, duration_seconds=rng.choice([1500, 1800, 2100]),
                                        distance_km=(Decimal("4.0") + Decimal(rng.choice([0, 5, 10])) / 10))
                    elif exercise.unit == "time":
                        workout.add_set(exercise, sets=3, duration_seconds=rng.choice([45, 60, 75]))
                    else:
                        weight = base.get(ex_name, Decimal("20.00")) * progress
                        workout.add_set(exercise, sets=rng.choice([3, 4]), reps=rng.choice([5, 6, 8, 10]),
                                        weight_kg=weight.quantize(Decimal("0.5")))

            Goal.objects.update_or_create(user=lifter, kind=Goal.Kind.WORKOUTS_PER_WEEK,
                                          active=True, defaults={"target": Decimal("4")})
            Goal.objects.update_or_create(user=lifter, kind=Goal.Kind.TOTAL_VOLUME,
                                          active=True, defaults={"target": Decimal("60000")})

            weight = Decimal("82.4") if lifter.username == "coach" else Decimal("61.8")
            for week in range(6, -1, -1):
                BodyWeight.objects.update_or_create(
                    user=lifter, date=today - timedelta(days=week * 3),
                    defaults={"weight_kg": (weight + Decimal(week) / Decimal(10)).quantize(Decimal("0.1"))},
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Exercise.objects.count()} exercises, {Workout.objects.count()} workouts, "
            f"{WorkoutSet.objects.count()} sets, {WorkoutSet.objects.filter(is_personal_best=True).count()} PRs."
        ))
