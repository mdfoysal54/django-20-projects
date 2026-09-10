"""QuizMaster views — browse, take, auto-grade, review and author quizzes."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CategoryForm, OptionFormSetFactory, QuestionForm, QuizForm, TakeQuizForm
from .models import Attempt, Category, Question, Quiz


def _live_quizzes():
    return (Quiz.objects.exclude(visibility=Quiz.Visibility.DRAFT)
            .select_related("author", "category")
            .annotate(n_questions=Count("questions", filter=Q(questions__active=True), distinct=True),
                      n_attempts=Count("attempts", distinct=True)))


def index(request):
    quizzes = _live_quizzes()
    return render(request, "quizmaster/index.html", {
        "featured": quizzes.filter(visibility=Quiz.Visibility.PUBLIC).order_by("-created")[:3],
        "popular": _live_quizzes().filter(visibility=Quiz.Visibility.PUBLIC).order_by("-n_attempts")[:6],
        "categories": Category.objects.annotate(n=Count("quizzes", filter=Q(quizzes__visibility="public"))),
        "total_quizzes": quizzes.filter(visibility=Quiz.Visibility.PUBLIC).count(),
        "total_attempts": Attempt.objects.filter(submitted_at__isnull=False).count(),
    })


def quiz_list(request):
    quizzes = _live_quizzes().filter(visibility=Quiz.Visibility.PUBLIC)
    category_slug = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "new")
    if category_slug:
        quizzes = quizzes.filter(category__slug=category_slug)
    if q:
        quizzes = quizzes.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if sort == "popular":
        quizzes = quizzes.order_by("-n_attempts")
    elif sort == "short":
        quizzes = quizzes.order_by("n_questions")
    else:
        quizzes = quizzes.order_by("-created")
    paginator = Paginator(quizzes, 9)
    return render(request, "quizmaster/quiz_list.html", {
        "page_obj": paginator.get_page(request.GET.get("page")), "q": q, "sort": sort,
        "category_slug": category_slug, "categories": Category.objects.all(),
    })


def quiz_detail(request, slug):
    quiz = get_object_or_404(Quiz.objects.select_related("author", "category"), slug=slug)
    if not quiz.can_view(request.user):
        raise Http404("No quiz found.")
    my_attempts = []
    if request.user.is_authenticated:
        my_attempts = quiz.attempts.filter(user=request.user).order_by("-started_at")
    return render(request, "quizmaster/quiz_detail.html", {
        "quiz": quiz, "stats": quiz.attempt_stats(), "my_attempts": my_attempts,
        "can_edit": quiz.can_edit(request.user),
        "in_progress": my_attempts.filter(submitted_at__isnull=True).first(),
        "attempts_left": not (quiz.one_attempt_only and my_attempts.exists()),
    })


@login_required
def start_attempt(request, slug):
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_view(request.user):
        raise Http404("No quiz found.")
    if request.method == "POST":
        attempt, error = quiz.start_attempt(request.user)
        if error:
            messages.error(request, error)
            return redirect(quiz)
        return redirect("take_quiz", pk=attempt.pk)
    return render(request, "quizmaster/quiz_intro.html", {
        "quiz": quiz,
        "attempts": quiz.attempts.filter(user=request.user).order_by("-started_at"),
        "stats": quiz.attempt_stats(),
    })


@login_required
def take_quiz(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("quiz"), pk=pk, user=request.user)
    if attempt.is_submitted:
        messages.info(request, "That attempt was already submitted — here are your results.")
        return redirect(attempt)

    deadline = None
    if attempt.quiz.time_limit_minutes:
        deadline = attempt.started_at + timedelta(minutes=attempt.quiz.time_limit_minutes)

    if request.method == "POST":
        # A one-page form is what the UI posts, but we also accept "?page" paging.
        if deadline and timezone.now() > deadline:
            attempt.submit()
            messages.warning(request, "Time is up — your answers were graded as they stand.")
            return redirect(attempt)
        form = TakeQuizForm(request.POST, quiz=attempt.quiz, attempt=attempt)
        if form.is_valid():
            form.save_answers(attempt)
            attempt.submit()
            messages.success(request, f"Submitted — you scored {attempt.score}/{attempt.max_score} "
                                      f"({attempt.percent}%).")
            return redirect(attempt)
        messages.error(request, "Some answers could not be read — please try again.")
    else:
        form = TakeQuizForm(quiz=attempt.quiz, attempt=attempt)

    # Pair each question with its own bound field so the template stays dumb.
    question_fields = [(question, form[f"q_{question.pk}"]) for question in form.questions]
    return render(request, "quizmaster/take_quiz.html", {
        "attempt": attempt, "quiz": attempt.quiz, "form": form, "questions": form.questions,
        "question_fields": question_fields,
        "deadline": deadline,
        "remaining_seconds": int((deadline - timezone.now()).total_seconds()) if deadline else None,
    })


@login_required
def attempt_result(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("quiz"), pk=pk)
    if attempt.user != request.user and not attempt.quiz.can_edit(request.user):
        raise Http404("No attempt found.")
    if not attempt.is_submitted:
        messages.info(request, "Finish the quiz to see your results.")
        return redirect("take_quiz", pk=attempt.pk)
    return render(request, "quizmaster/result.html", {
        "attempt": attempt, "quiz": attempt.quiz, "review": attempt.answers_review(),
        "leaderboard": _leaderboard(attempt.quiz),
    })


def _leaderboard(quiz, limit=5):
    return (quiz.attempts.filter(submitted_at__isnull=False)
            .select_related("user").order_by("-score", "submitted_at")[:limit])


@login_required
def my_attempts(request):
    attempts = (Attempt.objects.filter(user=request.user)
                .select_related("quiz").order_by("-started_at"))
    submitted = attempts.filter(submitted_at__isnull=False)
    scores = [a.percent for a in submitted]
    return render(request, "quizmaster/my_attempts.html", {
        "attempts": attempts,
        "submitted_count": submitted.count(),
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "best": max(scores) if scores else None,
        "passed": len([a for a in submitted if a.passed]),
    })


# ------------------------------------------------------------------ authoring
@login_required
def my_quizzes(request):
    quizzes = (Quiz.objects.filter(author=request.user)
               .annotate(n_questions=Count("questions", filter=Q(questions__active=True), distinct=True),
                         n_attempts=Count("attempts", distinct=True)))
    return render(request, "quizmaster/my_quizzes.html", {"quizzes": quizzes})


@login_required
def quiz_create(request):
    if request.method == "POST":
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.author = request.user
            quiz.visibility = Quiz.Visibility.DRAFT
            quiz.save()
            messages.success(request, "Quiz created — add its questions next.")
            return redirect("quiz_edit", slug=quiz.slug)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = QuizForm()
    return render(request, "quizmaster/quiz_form.html", {"form": form, "mode": "create"})


@login_required
def quiz_edit(request, slug):
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_edit(request.user):
        raise Http404("No quiz found.")
    if request.method == "POST":
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, "Quiz settings saved.")
            return redirect(quiz)
        messages.error(request, "Please fix the highlighted fields.")
    else:
        form = QuizForm(instance=quiz)
    return render(request, "quizmaster/quiz_form.html", {
        "form": form, "quiz": quiz, "mode": "edit",
        "questions": quiz.questions.prefetch_related("options"),
    })


@login_required
@require_POST
def quiz_delete(request, slug):
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_edit(request.user):
        raise Http404("No quiz found.")
    title = quiz.title
    quiz.delete()
    messages.success(request, f"“{title}” deleted.")
    return redirect("my_quizzes")


@login_required
def question_form(request, slug, pk=None):
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_edit(request.user):
        raise Http404("No quiz found.")
    question = get_object_or_404(Question, pk=pk, quiz=quiz) if pk else None

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        formset = OptionFormSetFactory(request.POST, instance=question, prefix="options")
        if form.is_valid() and formset.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()
            formset.instance = question
            formset.save()
            marked = question.correct_options().count()
            if marked == 0:
                messages.warning(request, "Saved, but no correct answer is marked — players can never score it.")
            else:
                messages.success(request, f"Question saved ({marked} correct answer"
                                          f"{'s' if marked != 1 else ''} marked).")
            return redirect("quiz_edit", slug=quiz.slug)
        messages.error(request, "Please fix the highlighted problems.")
    else:
        form = QuestionForm(instance=question)
        formset = OptionFormSetFactory(instance=question, prefix="options")
    return render(request, "quizmaster/question_form.html", {
        "quiz": quiz, "form": form, "formset": formset, "question": question,
    })


@login_required
@require_POST
def question_delete(request, slug, pk):
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_edit(request.user):
        raise Http404("No quiz found.")
    question = get_object_or_404(Question, pk=pk, quiz=quiz)
    question.delete()
    messages.success(request, "Question deleted.")
    return redirect("quiz_edit", slug=quiz.slug)


@login_required
def quiz_results(request, slug):
    """Author-only analytics for one quiz."""
    quiz = get_object_or_404(Quiz, slug=slug)
    if not quiz.can_edit(request.user):
        raise Http404("No quiz found.")
    attempts = quiz.attempts.filter(submitted_at__isnull=False).select_related("user").order_by("-score")
    question_stats = []
    for question in quiz.questions.prefetch_related("options"):
        answers = question.answers.filter(attempt__submitted_at__isnull=False)
        total = answers.count()
        correct = answers.filter(is_correct=True).count()
        question_stats.append({
            "question": question, "total": total, "correct": correct,
            "rate": round(100 * correct / total) if total else None,
        })
    question_stats.sort(key=lambda row: (row["rate"] is None, row["rate"] if row["rate"] is not None else 999))
    return render(request, "quizmaster/quiz_results.html", {
        "quiz": quiz, "attempts": attempts, "stats": quiz.attempt_stats(),
        "question_stats": question_stats,
        "pass_rate": quiz.attempt_stats()["pass_rate"],
    })


@login_required
def categories(request):
    form = CategoryForm()
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category added.")
            return redirect("categories")
    return render(request, "quizmaster/categories.html", {
        "form": form,
        "categories": Category.objects.annotate(n=Count("quizzes"), n_public=Count("quizzes", filter=Q(quizzes__visibility="public"))),
    })


@login_required
def profile(request):
    attempts = Attempt.objects.filter(user=request.user, submitted_at__isnull=False)
    scores = [a.percent for a in attempts]
    return render(request, "account/profile.html", {
        "quizzes": request.user.quizzes.count(),
        "published": request.user.quizzes.exclude(visibility=Quiz.Visibility.DRAFT).count(),
        "attempts": attempts.count(),
        "average": round(sum(scores) / len(scores), 1) if scores else None,
        "best": max(scores) if scores else None,
    })
