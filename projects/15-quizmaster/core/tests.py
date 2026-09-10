"""QuizMaster domain tests — auto-grading, answer-key secrecy, attempt rules."""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Answer, Attempt, Category, Option, Question, Quiz


def make_quiz(author, title="Django Basics", visibility=Quiz.Visibility.PUBLIC, **kw):
    return Quiz.objects.create(author=author, title=title, visibility=visibility,
                               pass_mark=kw.pop("pass_mark", 60), **kw)


def single(quiz, text, options, correct_index=0, points=1, order=0):
    question = Question.objects.create(quiz=quiz, kind=Question.Kind.SINGLE, text=text,
                                       points=points, order=order)
    for i, option in enumerate(options):
        Option.objects.create(question=question, text=option, is_correct=(i == correct_index), order=i)
    return question


def multi(quiz, text, options, correct_indexes, points=4, order=0):
    question = Question.objects.create(quiz=quiz, kind=Question.Kind.MULTI, text=text,
                                       points=points, order=order)
    for i, option in enumerate(options):
        Option.objects.create(question=question, text=option, is_correct=(i in correct_indexes), order=i)
    return question


def short(quiz, text, accepted, points=2, order=0):
    question = Question.objects.create(quiz=quiz, kind=Question.Kind.SHORT, text=text,
                                       points=points, order=order)
    for i, value in enumerate(accepted):
        Option.objects.create(question=question, text=value, is_correct=True, order=i)
    return question


class GradingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="Str0ng!Passw0rd")
        self.player = User.objects.create_user("player", password="Str0ng!Passw0rd")
        self.quiz = make_quiz(self.author)
        self.q1 = single(self.quiz, "Which HTTP method is idempotent?", ["GET", "POST", "PATCH"], 0, points=2)
        self.q2 = multi(self.quiz, "Pick every safe method", ["GET", "HEAD", "POST", "DELETE"], {0, 1}, points=4)
        self.q3 = short(self.quiz, "What does CSRF stand for?", ["cross site request forgery"], points=2)

    def answer(self, question):
        attempt, _ = self.quiz.start_attempt(self.player)
        return attempt, attempt.answer_for(question)

    def test_single_choice_correct_and_incorrect(self):
        attempt, answer = self.answer(self.q1)
        answer.selected_options.set([self.q1.options.first()])
        self.assertEqual(answer.grade(), 2)
        self.assertTrue(answer.is_correct)

        answer.selected_options.set([self.q1.options.last()])
        self.assertEqual(answer.grade(), 0)
        self.assertFalse(answer.is_correct)

    def test_multi_choice_requires_exactly_the_right_set(self):
        attempt, answer = self.answer(self.q2)
        correct = list(self.q2.correct_options())
        answer.selected_options.set(correct)
        self.assertEqual(answer.grade(), 4)

        answer.selected_options.set([correct[0]])                       # half the answers, no wrong picks
        self.assertEqual(answer.grade(), 2)
        self.assertFalse(answer.is_correct)

        answer.selected_options.set(self.q2.options.all())              # includes a wrong pick
        self.assertEqual(answer.grade(), 0)

    def test_short_answer_is_case_insensitive_and_trimmed(self):
        attempt, answer = self.answer(self.q3)
        answer.text_answer = "  Cross Site Request Forgery "
        self.assertEqual(answer.grade(), 2)
        answer.text_answer = "cross-site request forgery"
        self.assertEqual(answer.grade(), 0)                             # punctuation matters

    def test_blank_answers_score_zero_and_never_explode(self):
        attempt, answer = self.answer(self.q3)
        answer.text_answer = ""
        self.assertEqual(answer.grade(), 0)
        attempt2, a2 = self.answer(self.q2)
        self.assertEqual(a2.grade(), 0)

    def test_submit_grades_whole_paper_and_freezes_it(self):
        attempt, answer = self.answer(self.q1)
        answer.selected_options.set([self.q1.options.first()])
        attempt.submit()
        self.assertTrue(attempt.is_submitted)
        self.assertEqual(attempt.score, 2)          # 2 of 8 points on the paper
        self.assertEqual(attempt.max_score, 8)
        self.assertEqual(attempt.percent, 25)
        self.assertFalse(attempt.passed)

    def test_resubmitting_does_not_change_the_score(self):
        attempt, answer = self.answer(self.q1)
        answer.selected_options.set([self.q1.options.first()])
        attempt.submit()
        score = attempt.score
        attempt.submit()                                                # idempotent
        self.assertEqual(attempt.score, score)

    def test_perfect_paper_passes(self):
        attempt, _ = self.quiz.start_attempt(self.player)
        # record_answer persists in one call — the safe way to script a paper.
        attempt.record_answer(self.q1, options=self.q1.options.first())
        attempt.record_answer(self.q2, options=list(self.q2.correct_options()))
        attempt.record_answer(self.q3, text="cross site request forgery")
        attempt.submit()
        self.assertEqual(attempt.score, 8)
        self.assertEqual(attempt.percent, 100)
        self.assertTrue(attempt.passed)

    def test_question_with_no_correct_option_scores_nobody(self):
        broken = single(self.quiz, "An ambiguous question here", ["A", "B"], correct_index=-1, points=3, order=9)
        attempt, answer = self.quiz.start_attempt(self.player)
        answer = attempt.answer_for(broken)
        answer.selected_options.set([broken.options.first()])
        self.assertEqual(answer.grade(), 0)


class AttemptRulesTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="Str0ng!Passw0rd")
        self.player = User.objects.create_user("player", password="Str0ng!Passw0rd")
        self.quiz = make_quiz(self.author)
        self.q1 = single(self.quiz, "Is HTTP stateless?", ["Yes", "No"], 0)

    def test_unfinished_attempt_is_resumed_not_duplicated(self):
        first, error = self.quiz.start_attempt(self.player)
        self.assertIsNone(error)
        second, error = self.quiz.start_attempt(self.player)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Attempt.objects.filter(user=self.player).count(), 1)

    def test_one_attempt_only_quiz_refuses_a_second_after_submitting(self):
        self.quiz.one_attempt_only = True
        self.quiz.save(update_fields=["one_attempt_only"])
        attempt, _ = self.quiz.start_attempt(self.player)
        attempt.submit()
        again, error = self.quiz.start_attempt(self.player)
        self.assertIsNone(again)
        self.assertIn("only one attempt", error)

    def test_retake_allowed_when_not_limited(self):
        attempt, _ = self.quiz.start_attempt(self.player)
        attempt.submit()
        again, error = self.quiz.start_attempt(self.player)
        self.assertIsNone(error)
        self.assertNotEqual(attempt.pk, again.pk)

    def test_quiz_without_questions_cannot_start(self):
        empty = make_quiz(self.author, "Empty quiz")
        attempt, error = empty.start_attempt(self.player)
        self.assertIsNone(attempt)
        self.assertIn("no questions", error)

    def test_anonymous_cannot_start(self):
        from django.contrib.auth.models import AnonymousUser
        attempt, error = self.quiz.start_attempt(AnonymousUser())
        self.assertIsNone(attempt)

    def test_attempt_stats(self):
        for i, correct in enumerate([True, False, True]):
            user = User.objects.create_user(f"p{i}", password="Str0ng!Passw0rd")
            attempt, _ = self.quiz.start_attempt(user)
            answer = attempt.answer_for(self.q1)
            if correct:
                answer.selected_options.set([self.q1.options.first()])
            attempt.submit()
        stats = self.quiz.attempt_stats()
        self.assertEqual(stats["count"], 3)
        self.assertEqual(stats["pass_rate"], 67)
        self.assertEqual(stats["best"], 100)


class AnswerKeyPrivacyTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="Str0ng!Passw0rd")
        self.player = User.objects.create_user("player", password="Str0ng!Passw0rd")
        self.quiz = make_quiz(self.author, visibility=Quiz.Visibility.PUBLIC)
        self.q1 = single(self.quiz, "Which port does HTTPS use?", ["443", "80", "22"], 0)

    def test_taking_page_never_reveals_which_option_is_correct(self):
        attempt, _ = self.quiz.start_attempt(self.player)
        self.client.force_login(self.player)
        html = self.client.get(reverse("take_quiz", kwargs={"pk": attempt.pk})).content.decode()
        self.assertIn("Which port", html)
        self.assertNotIn("is_correct", html)
        self.assertNotIn("value=\"correct\"", html)
        # The correct option must not be identifiable by any marker in the page.
        self.assertNotIn("answer-key", html)

    def test_draft_quiz_is_404_for_players(self):
        draft = make_quiz(self.author, "Secret Draft Quiz", visibility=Quiz.Visibility.DRAFT)
        single(draft, "Hidden question text", ["Yes", "No"])
        self.client.force_login(self.player)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(reverse("start_attempt", kwargs={"slug": draft.slug})).status_code, 404)

    def test_author_sees_their_draft(self):
        draft = make_quiz(self.author, "Secret Draft Quiz", visibility=Quiz.Visibility.DRAFT)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 200)

    def test_another_player_cannot_view_or_take_your_attempt(self):
        attempt, _ = self.quiz.start_attempt(self.player)
        attempt.submit()
        intruder = User.objects.create_user("intruder", password="Str0ng!Passw0rd")
        self.client.force_login(intruder)
        self.assertEqual(self.client.get(reverse("attempt_result", kwargs={"pk": attempt.pk})).status_code, 404)
        self.assertEqual(self.client.get(reverse("take_quiz", kwargs={"pk": attempt.pk})).status_code, 404)

    def test_quiz_author_can_review_attempts(self):
        attempt, _ = self.quiz.start_attempt(self.player)
        attempt.submit()
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("attempt_result", kwargs={"pk": attempt.pk})).status_code, 200)

    def test_rival_cannot_edit_or_delete_your_quiz(self):
        rival = User.objects.create_user("rival", password="Str0ng!Passw0rd")
        self.client.force_login(rival)
        self.assertEqual(self.client.get(reverse("quiz_edit", kwargs={"slug": self.quiz.slug})).status_code, 404)
        self.assertEqual(self.client.post(reverse("quiz_delete", kwargs={"slug": self.quiz.slug})).status_code, 404)
        self.assertTrue(Quiz.objects.filter(pk=self.quiz.pk).exists())

    def test_results_analytics_are_author_only(self):
        self.client.force_login(self.player)
        self.assertEqual(self.client.get(reverse("quiz_results", kwargs={"slug": self.quiz.slug})).status_code, 404)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("quiz_results", kwargs={"slug": self.quiz.slug})).status_code, 200)


class TakeQuizFlowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", password="Str0ng!Passw0rd")
        self.player = User.objects.create_user("player", password="Str0ng!Passw0rd")
        self.quiz = make_quiz(self.author, visibility=Quiz.Visibility.PUBLIC)
        self.q1 = single(self.quiz, "Which keyword defines a function in Python?", ["def", "func", "lambda"], 0)
        self.q2 = multi(self.quiz, "Which of these are Python builtins?", ["len", "print", "printf"], {0, 1}, points=2)

    def test_full_flow_from_start_to_result(self):
        self.client.force_login(self.player)
        response = self.client.post(reverse("start_attempt", kwargs={"slug": self.quiz.slug}))
        attempt_id = int(response.url.rstrip("/").split("/")[-1])
        response = self.client.post(reverse("take_quiz", kwargs={"pk": attempt_id}), {
            f"q_{self.q1.pk}": self.q1.options.first().pk,
            f"q_{self.q2.pk}": [str(o.pk) for o in self.q2.correct_options()],
        })
        self.assertEqual(response.status_code, 302)
        attempt = Attempt.objects.get(pk=attempt_id)
        self.assertTrue(attempt.is_submitted)
        self.assertEqual(attempt.score, attempt.max_score)              # both right

        result = self.client.get(reverse("attempt_result", kwargs={"pk": attempt_id}))
        self.assertContains(result, "Passed")
        self.assertContains(result, "def")

    def test_wrong_answers_produce_a_failing_result(self):
        self.client.force_login(self.player)
        attempt, _ = self.quiz.start_attempt(self.player)
        self.client.post(reverse("take_quiz", kwargs={"pk": attempt.pk}), {
            f"q_{self.q1.pk}": self.q1.options.last().pk,               # "lambda"
        })
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 0)
        self.assertFalse(attempt.passed)

    def test_result_page_shows_the_correct_answer_after_submission(self):
        self.client.force_login(self.player)
        attempt, _ = self.quiz.start_attempt(self.player)
        self.client.post(reverse("take_quiz", kwargs={"pk": attempt.pk}), {
            f"q_{self.q1.pk}": self.q1.options.last().pk,
        })
        result = self.client.get(reverse("attempt_result", kwargs={"pk": attempt.pk}))
        self.assertContains(result, "Correct answer")

    def test_quiz_without_a_login_redirects(self):
        response = self.client.post(reverse("start_attempt", kwargs={"slug": self.quiz.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)


class SeederTests(TestCase):
    def test_seed_demo_populates_quizzes(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Quiz.objects.count(), 4)
        self.assertGreaterEqual(Question.objects.count(), 15)
        self.assertTrue(Option.objects.exists())
        self.assertTrue(Attempt.objects.filter(submitted_at__isnull=False).exists())
        self.assertTrue(Category.objects.exists())
        # Every published quiz must be answerable: at least one correct option per question.
        for quiz in Quiz.objects.exclude(visibility=Quiz.Visibility.DRAFT):
            for question in quiz.questions.all():
                self.assertTrue(question.correct_options().exists(),
                                f"{quiz.title}: “{question.text}” has no correct answer")
