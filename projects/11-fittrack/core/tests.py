"""FitTrack domain tests — volume maths, PR detection, streaks, privacy."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BodyWeight, Exercise, Goal, Workout, WorkoutSet, current_streak, week_summary


def make_workout(user, title="Push day", days_ago=0, duration=60):
    return Workout.objects.create(user=user, title=title, date=timezone.localdate() - timedelta(days=days_ago),
                                  duration_minutes=duration)


class VolumeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lifter", password="Str0ng!Passw0rd")
        self.bench = Exercise.objects.create(name="Bench Press", muscle_group="chest", unit="reps", is_compound=True)
        self.workout = make_workout(self.user)

    def test_volume_is_sets_times_reps_times_weight(self):
        entry = self.workout.add_set(self.bench, sets=4, reps=8, weight_kg=Decimal("80.00"))
        self.assertEqual(entry.volume_kg, Decimal("2560.00"))
        self.assertEqual(self.workout.total_volume, Decimal("2560.00"))
        self.assertEqual(self.workout.total_sets, 4)

    def test_unweighted_sets_have_zero_volume_but_still_count(self):
        entry = self.workout.add_set(self.bench, sets=3, reps=10, weight_kg=None)
        self.assertEqual(entry.volume_kg, Decimal("0"))
        self.assertEqual(self.workout.total_sets, 3)

    def test_volume_is_decimal_not_float(self):
        entry = self.workout.add_set(self.bench, sets=3, reps=5, weight_kg=Decimal("72.50"))
        self.assertIsInstance(entry.volume_kg, Decimal)
        self.assertEqual(entry.volume_kg, Decimal("1087.50"))


class PersonalBestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lifter", password="Str0ng!Passw0rd")
        self.squat = Exercise.objects.create(name="Back Squat", muscle_group="legs", unit="reps", is_compound=True)
        self.workout = make_workout(self.user)

    def test_first_heavy_set_is_a_personal_best(self):
        entry = self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        self.assertTrue(entry.is_personal_best)

    def test_lighter_set_is_not_a_pr(self):
        self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        lighter = self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("90.00"))
        self.assertFalse(lighter.is_personal_best)

    def test_heavier_set_flags_a_pr(self):
        self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        heavier = self.workout.add_set(self.squat, sets=3, reps=3, weight_kg=Decimal("110.00"))
        self.assertTrue(heavier.is_personal_best)

    def test_more_volume_at_same_weight_is_a_pr(self):
        self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        more = self.workout.add_set(self.squat, sets=5, reps=5, weight_kg=Decimal("100.00"))
        self.assertTrue(more.is_personal_best)

    def test_cardio_pr_uses_duration_and_distance(self):
        run = Exercise.objects.create(name="Running", muscle_group="cardio", unit="distance")
        first = self.workout.add_set(run, sets=1, duration_seconds=1500, distance_km=Decimal("5.00"))
        self.assertTrue(first.is_personal_best)
        faster = self.workout.add_set(run, sets=1, duration_seconds=1800, distance_km=Decimal("6.00"))
        self.assertTrue(faster.is_personal_best)       # longer run = PR
        shorter = self.workout.add_set(run, sets=1, duration_seconds=600, distance_km=Decimal("2.00"))
        self.assertFalse(shorter.is_personal_best)

    def test_best_for_reports_the_heaviest_set(self):
        self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        self.workout.add_set(self.squat, sets=3, reps=3, weight_kg=Decimal("115.00"))
        best = self.squat.best_for(self.user)
        self.assertEqual(best.weight_kg, Decimal("115.00"))

    def test_prs_are_scoped_to_the_user(self):
        other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        other_workout = make_workout(other, "Other leg day")
        other_workout.add_set(self.squat, sets=5, reps=5, weight_kg=Decimal("140.00"))
        entry = self.workout.add_set(self.squat, sets=3, reps=5, weight_kg=Decimal("100.00"))
        self.assertTrue(entry.is_personal_best)        # not compared against another user


class StreakAndSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lifter", password="Str0ng!Passw0rd")

    def test_no_workouts_means_no_streak(self):
        self.assertEqual(current_streak(self.user), 0)

    def test_consecutive_days_count_up(self):
        for days_ago in range(4):
            make_workout(self.user, title=f"Day {days_ago}", days_ago=days_ago)
        self.assertEqual(current_streak(self.user), 4)

    def test_gap_breaks_the_streak(self):
        make_workout(self.user, title="Today", days_ago=0)
        make_workout(self.user, title="Two days back", days_ago=2)
        self.assertEqual(current_streak(self.user), 1)

    def test_yesterday_only_still_counts(self):
        make_workout(self.user, title="Yesterday", days_ago=1)
        self.assertEqual(current_streak(self.user), 1)

    def test_week_summary_totals(self):
        workout = make_workout(self.user, title="Today", days_ago=0, duration=70)
        bench = Exercise.objects.create(name="Bench Press", muscle_group="chest")
        workout.add_set(bench, sets=4, reps=8, weight_kg=Decimal("70.00"))
        # A workout from last month must not appear in this week's totals.
        make_workout(self.user, title="Old", days_ago=40, duration=90)
        summary = week_summary(self.user)
        self.assertEqual(summary["workouts"], 1)
        self.assertEqual(summary["minutes"], 70)
        self.assertEqual(summary["volume"], Decimal("2240.00"))
        self.assertEqual(summary["prs"], 1)


class GoalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lifter", password="Str0ng!Passw0rd")

    def test_workout_goal_progress(self):
        goal = Goal.objects.create(user=self.user, kind=Goal.Kind.WORKOUTS_PER_WEEK, target=3)
        for i in range(3):
            make_workout(self.user, title=f"Session {i}", days_ago=i)
        self.assertEqual(goal.current_value(), Decimal("3"))
        self.assertEqual(goal.progress_percent, 100)
        self.assertTrue(goal.is_complete)

    def test_volume_goal_progress_is_capped_at_100(self):
        goal = Goal.objects.create(user=self.user, kind=Goal.Kind.TOTAL_VOLUME, target=Decimal("100.00"))
        workout = make_workout(self.user, title="Big day")
        bench = Exercise.objects.create(name="Bench Press", muscle_group="chest")
        workout.add_set(bench, sets=5, reps=5, weight_kg=Decimal("100.00"))
        self.assertEqual(goal.current_value(), Decimal("2500.00"))
        self.assertEqual(goal.progress_percent, 100)

    def test_only_one_active_goal_per_kind_in_the_database(self):
        Goal.objects.create(user=self.user, kind=Goal.Kind.WORKOUTS_PER_WEEK, target=3)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Goal.objects.create(user=self.user, kind=Goal.Kind.WORKOUTS_PER_WEEK, target=5)

    def test_saving_a_new_goal_replaces_the_active_one(self):
        Goal.objects.create(user=self.user, kind=Goal.Kind.WORKOUTS_PER_WEEK, target=3)
        self.client.force_login(self.user)
        self.client.post(reverse("goals"), {"kind": "workouts_week", "target": "5"})
        active = Goal.objects.filter(user=self.user, kind=Goal.Kind.WORKOUTS_PER_WEEK, active=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().target, Decimal("5.00"))


class OwnedDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("lifter", password="Str0ng!Passw0rd")
        self.stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.workout = make_workout(self.user, "Private session")
        self.bench = Exercise.objects.create(name="Bench Press", muscle_group="chest")
        self.entry = self.workout.add_set(self.bench, sets=3, reps=8, weight_kg=Decimal("60.00"))

    def test_workout_is_private(self):
        self.client.force_login(self.stranger)
        for url in [reverse("workout_detail", kwargs={"pk": self.workout.pk}),
                    reverse("workout_edit", kwargs={"pk": self.workout.pk})]:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_stranger_cannot_delete_or_add_sets(self):
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.post(reverse("delete_set", kwargs={"pk": self.entry.pk})).status_code, 404)
        self.assertEqual(self.client.post(reverse("add_set", kwargs={"pk": self.workout.pk}),
                                          {"exercise": self.bench.pk, "sets": 3, "reps": 5}).status_code, 404)
        self.assertEqual(self.client.post(reverse("delete_workout", kwargs={"pk": self.workout.pk})).status_code, 404)
        self.assertTrue(Workout.objects.filter(pk=self.workout.pk).exists())

    def test_future_workouts_are_rejected(self):
        self.client.force_login(self.user)
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(reverse("workout_create"),
                                    {"title": "Time travel", "date": tomorrow, "duration_minutes": 45, "feel": "good"},
                                    follow=True)
        self.assertContains(response, "cannot log a workout in the future")
        self.assertEqual(Workout.objects.filter(user=self.user).count(), 1)

    def test_duplicate_title_on_the_same_day_is_rejected_by_the_db(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Workout.objects.create(user=self.user, title="Private session", date=self.workout.date)

    def test_one_bodyweight_entry_per_day_via_form(self):
        self.client.force_login(self.user)
        today = timezone.localdate().isoformat()
        self.client.post(reverse("log_weight"), {"date": today, "weight_kg": "78.50"})
        self.client.post(reverse("log_weight"), {"date": today, "weight_kg": "78.20"})
        entries = BodyWeight.objects.filter(user=self.user, date=today)
        self.assertEqual(entries.count(), 1)
        self.assertEqual(entries.first().weight_kg, Decimal("78.20"))


class SeederTests(TestCase):
    def test_seed_demo_populates_tracker(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Exercise.objects.count(), 12)
        self.assertGreaterEqual(Workout.objects.count(), 6)
        self.assertTrue(WorkoutSet.objects.filter(is_personal_best=True).exists())
        self.assertTrue(Goal.objects.filter(active=True).exists())
        self.assertTrue(BodyWeight.objects.exists())
