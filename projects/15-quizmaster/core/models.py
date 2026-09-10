"""QuizMaster models — quizzes, questions, attempts and server-side auto-grading.

Design rules that the tests pin down:

* the answer key never reaches the browser before submission;
* `Question.grade_answer()` scores one answer; `Attempt.submit()` scores the whole paper;
* a one-attempt-per-user quiz is enforced by the database;
* scores are computed from the stored answers, so replays can be re-graded.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    emoji = models.CharField(max_length=8, default="📚")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Quiz(models.Model):
    class Visibility(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLIC = "public", "Public"
        UNLISTED = "unlisted", "Unlisted (link only)"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quizzes")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="quizzes")
    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(blank=True)
    emoji = models.CharField(max_length=8, default="🧠")
    visibility = models.CharField(max_length=8, choices=Visibility.choices, default=Visibility.DRAFT)
    pass_mark = models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(1)],
                                                 help_text="Percentage needed to pass.")
    time_limit_minutes = models.PositiveSmallIntegerField(default=0,
                                                          help_text="0 = no time limit.")
    one_attempt_only = models.BooleanField(default=False)
    shuffle_questions = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["visibility", "-created"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:60] or "quiz"
            slug, n = base, 1
            while Quiz.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("quiz_detail", kwargs={"slug": self.slug})

    # ---------------------------------------------------------------- derived
    @property
    def question_count(self) -> int:
        return self.questions.filter(active=True).count()

    @property
    def total_points(self) -> int:
        return sum(q.points for q in self.questions.filter(active=True))

    @property
    def is_published(self) -> bool:
        return self.visibility != self.Visibility.DRAFT

    def can_view(self, user) -> bool:
        if self.visibility == self.Visibility.PUBLIC:
            return True
        if self.visibility == self.Visibility.UNLISTED:
            return True                       # reachable, just not listed
        return bool(user.is_authenticated and (user == self.author or user.is_staff))

    def can_edit(self, user) -> bool:
        return bool(user.is_authenticated and (user == self.author or user.is_staff))

    def attempt_stats(self):
        attempts = self.attempts.filter(submitted_at__isnull=False)
        count = attempts.count()
        if not count:
            return {"count": 0, "average": None, "pass_rate": None, "best": None, "worst": None}
        scores = [a.percent for a in attempts]
        passed = len([s for s in scores if s >= self.pass_mark])
        return {"count": count, "average": round(sum(scores) / count, 1),
                "pass_rate": round(100 * passed / count), "best": max(scores), "worst": min(scores)}

    def start_attempt(self, user):
        """Begin (or resume) an attempt for the whole quiz."""
        if not user.is_authenticated:
            return None, "Log in to take this quiz."
        if not self.questions.filter(active=True).exists():
            return None, "This quiz has no questions yet."
        existing = self.attempts.filter(user=user).order_by("-started_at").first()
        if existing and existing.submitted_at is None:
            return existing, None                    # resume the unfinished attempt
        if self.one_attempt_only and existing is not None:
            return None, "You have already taken this quiz — only one attempt is allowed."
        attempt = Attempt.objects.create(quiz=self, user=user, max_score=self.total_points)
        return attempt, None


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Single choice"
        MULTI = "multi", "Multiple choice"
        TRUE_FALSE = "truefalse", "True / false"
        SHORT = "short", "Short answer"

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=9, choices=Kind.choices, default=Kind.SINGLE)
    text = models.CharField(max_length=300)
    points = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    explanation = models.CharField(max_length=300, blank=True,
                                   help_text="Shown after the attempt is submitted.")
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.text[:70]

    @property
    def choices(self):
        return self.options.all()

    def correct_options(self):
        return self.options.filter(is_correct=True)

    def correct_texts(self):
        return [o.text.strip().lower() for o in self.correct_options()]

    # ----------------------------------------------------------------- grading
    def grade_answer(self, answer):
        """Return (points_awarded, is_correct) for one submitted answer.

        Named `grade_answer` rather than `check` because Django reserves
        `Model.check()` for the system-check framework.
        """
        if self.kind in (self.Kind.SINGLE, self.Kind.TRUE_FALSE):
            correct = self.correct_options().values_list("pk", flat=True)
            chosen = answer.selected_options.values_list("pk", flat=True)
            return (self.points, True) if set(correct) and set(correct) == set(chosen) else (0, False)
        if self.kind == self.Kind.MULTI:
            correct = set(self.correct_options().values_list("pk", flat=True))
            chosen = set(answer.selected_options.values_list("pk", flat=True))
            if not correct or not chosen:
                return 0, False
            if correct == chosen:
                return self.points, True
            # Partial credit: no wrong picks, at least half of the right ones.
            if chosen.issubset(correct) and len(chosen) >= max(1, len(correct) // 2):
                return max(1, round(self.points / 2)), False
            return 0, False
        # Short answer: exact (case-insensitive) match against any accepted form.
        given = (answer.text_answer or "").strip().lower()
        return (self.points, True) if given and given in self.correct_texts() else (0, False)


class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=240)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{'✓' if self.is_correct else '·'} {self.text[:50]}"


class Attempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    max_score = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["quiz", "user"])]

    def __str__(self):
        state = "submitted" if self.submitted_at else "in progress"
        return f"{self.user.username} · {self.quiz.title} ({state})"

    def get_absolute_url(self):
        return reverse("attempt_result", kwargs={"pk": self.pk})

    @property
    def percent(self) -> int:
        if not self.max_score:
            return 0
        return round(100 * self.score / self.max_score)

    @property
    def passed(self) -> bool:
        return self.submitted_at is not None and self.percent >= self.quiz.pass_mark

    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None

    @property
    def time_taken_seconds(self):
        if not self.submitted_at:
            return None
        return int((self.submitted_at - self.started_at).total_seconds())

    def answer_for(self, question):
        """The (unsaved) Answer row for a question — set fields then call `save()`."""
        answer, _ = Answer.objects.get_or_create(attempt=self, question=question)
        return answer

    def record_answer(self, question, options=(), text=""):
        """Persist one answer in a single call — the scripting counterpart to the form.

        `options` may be a single Option or an iterable of them.
        """
        answer = self.answer_for(question)
        if options:
            if not isinstance(options, (list, tuple, set)):
                options = [options]
            answer.selected_options.set(options)
            answer.text_answer = ""
        else:
            answer.selected_options.clear()
            answer.text_answer = text or ""
        answer.save()
        return answer

    @transaction.atomic
    def submit(self):
        """Grade every answer from stored data and freeze the attempt."""
        if self.is_submitted:
            return self
        total = 0
        for question in self.quiz.questions.filter(active=True):
            answer, _ = Answer.objects.get_or_create(attempt=self, question=question)
            answer.grade()
            total += answer.points_awarded
        self.score = total
        self.max_score = self.quiz.total_points
        self.submitted_at = timezone.now()
        self.save(update_fields=["score", "max_score", "submitted_at"])
        return self

    def answers_review(self):
        rows = []
        for answer in self.answers.select_related("question").prefetch_related("selected_options"):
            question = answer.question
            rows.append({
                "question": question,
                "answer": answer,
                "correct": answer.is_correct,
                "awarded": answer.points_awarded,
                "expected": ", ".join(question.correct_texts()) if question.kind == Question.Kind.SHORT
                            else ", ".join(question.correct_options().values_list("text", flat=True)),
                "given": ", ".join(answer.selected_options.values_list("text", flat=True))
                         or answer.text_answer or "—",
            })
        return rows


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    selected_options = models.ManyToManyField(Option, blank=True, related_name="answers")
    text_answer = models.CharField(max_length=240, blank=True)
    points_awarded = models.PositiveSmallIntegerField(default=0)
    is_correct = models.BooleanField(default=False)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["question__order", "pk"]
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="one_answer_per_question")]

    def __str__(self):
        return f"Answer to {self.question_id}"

    def grade(self):
        """Score this answer and persist both the score *and* the submitted text.

        Saving `text_answer` here matters: a caller that sets the attribute in
        memory (rather than through a form) would otherwise be graded against a
        blank answer that was never written to the database.
        """
        self.points_awarded, self.is_correct = self.question.grade_answer(self)
        self.graded_at = timezone.now()
        self.save(update_fields=["points_awarded", "is_correct", "graded_at", "text_answer"])
        return self.points_awarded
