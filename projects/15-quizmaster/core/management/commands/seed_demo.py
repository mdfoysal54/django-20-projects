"""Seed QuizMaster with categories, quizzes, questions and a few graded attempts."""
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Attempt, Category, Option, Question, Quiz

CATEGORIES = [("Web Development", "🌐"), ("Python", "🐍"), ("Databases", "🗄️"),
              ("Security", "🔒"), ("General Knowledge", "🌍")]

QUIZZES = [
    ("Django Fundamentals", "Web Development", "🧠", "public", 60, 10, False,
     "Models, views, templates and the request cycle — the essentials every Django developer should know.",
     [
         ("single", "What does `manage.py migrate` do?", ["Applies database migrations", "Creates a new app",
                                                           "Runs the test suite", "Starts the dev server"], 0, 1,
          "Migrations translate model changes into database schema changes."),
         ("single", "Which file maps URLs to views by default?", ["urls.py", "views.py", "settings.py", "admin.py"], 0, 1,
          "urls.py holds the URL configuration; it can be split per app."),
         ("multi", "Which of these are Django ORM query methods?",
          ["filter()", "exclude()", "select_related()", "render()"], {0, 1, 2}, 2,
          "render() is a shortcut for building an HttpResponse — not a queryset method."),
         ("single", "What protects POST forms from cross-site request forgery?",
          ["The {% csrf_token %} template tag", "The CSRF cookie alone", "SECRET_KEY", "AUTH_PASSWORD_VALIDATORS"], 0, 1,
          "The token plus the cookie must match — a cross-site page cannot read the token."),
         ("truefalse", "Django's default `User` model stores passwords in plain text.", ["False", "True"], 0, 1,
          "Passwords are hashed with PBKDF2 by default — never stored in plain text."),
         ("short", "Which command creates new migration files from model changes?",
          ["makemigrations"], None, 2, "`makemigrations` writes the files; `migrate` applies them."),
     ]),
    ("Python Essentials", "Python", "🐍", "public", 70, 0, False,
     "Syntax, data structures and the standard library — a warm-up for interviews.",
     [
         ("single", "What is the output of `len('quizzes')`?", ["7", "6", "8", "Error"], 0, 1,
          "Seven characters: q-u-i-z-z-e-s."),
         ("multi", "Which of these are immutable in Python?",
          ["tuple", "str", "list", "int"], {0, 1, 3}, 2, "Lists are mutable; tuples, strings and ints are not."),
         ("single", "Which data structure gives O(1) average lookup by key?",
          ["dict", "list", "tuple", "set of tuples"], 0, 1, "Dictionary lookups are hash-based."),
         ("short", "Which keyword defines a function in Python?", ["def"], None, 2,
          "`def name(args):` is the function definition syntax."),
         ("single", "What does a list comprehension return?", ["A new list", "A generator", "None", "The input list, mutated"],
          0, 1, "A list comprehension builds a brand-new list."),
     ]),
    ("Databases & SQL", "Databases", "🗄️", "public", 60, 15, True,
     "Indexes, transactions and the query planner — one attempt only, so make it count.",
     [
         ("single", "Which SQL clause filters rows before grouping?", ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 0, 1,
          "HAVING filters after aggregation; WHERE filters individual rows."),
         ("multi", "Which database levels does ACID cover?",
          ["Atomicity", "Consistency", "Isolation", "Availability"], {0, 1, 2}, 2,
          "Availability belongs to the CAP theorem, not ACID."),
         ("single", "What does an index primarily trade away?", ["Write speed and storage", "Read speed", "Durability",
                                                                 "Referential integrity"], 0, 1,
          "Every index must be maintained on write — that costs time and disk."),
         ("truefalse", "SELECT without ORDER BY guarantees a stable row order.", ["False", "True"], 0, 1,
          "Without ORDER BY the database may return rows in any order."),
         ("short", "Which statement starts a database transaction in SQL?", ["begin", "begin transaction"], None, 2,
          "BEGIN (or BEGIN TRANSACTION) opens an explicit transaction."),
     ]),
    ("Web Security Basics", "Security", "🔒", "public", 75, 0, False,
     "The vulnerabilities that show up in real code reviews, and how to close them.",
     [
         ("single", "Which is the best defence against SQL injection?", ["Parameterised queries", "Escaping quotes by hand",
                                                                          "Hiding error messages", "Using HTTPS"], 0, 1,
          "Parameter binding keeps data out of the SQL grammar entirely."),
         ("multi", "Which of these should be server-side checks?",
          ["Ownership of the object", "File upload size", "Money rounding", "Font choice"], {0, 1, 2}, 2,
          "Anything that affects data or money belongs on the server."),
         ("single", "What does a Content Security Policy reduce?", ["Cross-site scripting impact", "Password reuse",
                                                                    "Server CPU load", "Email spoofing"], 0, 1,
          "A strict CSP limits what an injected script can actually do."),
         ("short", "Which HTTP-only cookie flag prevents JavaScript from reading the cookie?",
          ["httponly"], None, 2, "HttpOnly keeps session cookies away from document.cookie."),
     ]),
    ("Draft: Advanced ORM", "Python", "🧪", "draft", 60, 0, False,
     "Work in progress — subqueries, prefetch_related and window functions.",
     [
         ("single", "What does `select_for_update()` do?", ["Locks the selected rows until the transaction ends",
                                                            "Caches the queryset", "Skips rows with NULL", "Runs the query twice"],
          0, 1, "It emits SELECT … FOR UPDATE, taking row locks."),
     ]),
]

PLAYERS = ["nadia", "rakib", "marufa", "sabbir", "tanvir"]


class Command(BaseCommand):
    help = "Create demo quizzes, questions and graded attempts."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        rng = random.Random(1509)

        for username, staff in [("quizmaster", False), ("admin", True)] + [(p, False) for p in PLAYERS]:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"email": f"{username}@quizmaster.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = True
                user.is_superuser = True
            user.save()

        for name, emoji in CATEGORIES:
            Category.objects.get_or_create(name=name, defaults={"emoji": emoji})

        author = User.objects.get(username="quizmaster")

        for title, category, emoji, visibility, pass_mark, time_limit, one_attempt, description, questions in QUIZZES:
            quiz, created = Quiz.objects.get_or_create(
                author=author, title=title,
                defaults={"category": Category.objects.get(name=category), "emoji": emoji,
                          "visibility": visibility, "pass_mark": pass_mark,
                          "time_limit_minutes": time_limit, "one_attempt_only": one_attempt,
                          "description": description, "shuffle_questions": True},
            )
            if not created:
                continue
            for order, (kind, text, options, correct, points, explanation) in enumerate(questions):
                question = Question.objects.create(quiz=quiz, kind=kind, text=text,
                                                   points=points, explanation=explanation, order=order)
                if kind == "short":
                    for i, accepted in enumerate(correct or ["answer"]):
                        Option.objects.create(question=question, text=accepted, is_correct=True, order=i)
                    continue
                correct_set = correct if isinstance(correct, set) else {correct}
                for i, option in enumerate(options):
                    Option.objects.create(question=question, text=option,
                                          is_correct=(i in correct_set), order=i)

        # A handful of graded attempts so leaderboards and analytics are not empty.
        quizzes = list(Quiz.objects.exclude(visibility=Quiz.Visibility.DRAFT))
        for i, username in enumerate(PLAYERS):
            player = User.objects.get(username=username)
            for quiz in quizzes[: 2 + i % 2]:
                if quiz.one_attempt_only and quiz.attempts.filter(user=player).exists():
                    continue
                attempt, error = quiz.start_attempt(player)
                if error or attempt is None:
                    continue
                # Better players get more right — deterministic, so charts stay stable.
                skill = 0.55 + 0.1 * i
                for question in quiz.questions.all():
                    answer = attempt.answer_for(question)
                    correct = list(question.correct_options())
                    if not correct:
                        continue
                    if rng.random() < skill:
                        if question.kind == Question.Kind.MULTI:
                            answer.selected_options.set(correct)
                        elif question.kind == Question.Kind.SHORT:
                            answer.text_answer = correct[0].text
                        else:
                            answer.selected_options.set([correct[0]])
                    else:
                        wrong = [o for o in question.options.all() if not o.is_correct]
                        if question.kind == Question.Kind.SHORT:
                            answer.text_answer = "not sure"
                        elif wrong:
                            answer.selected_options.set([wrong[0]])
                attempt.submit()

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Quiz.objects.count()} quizzes, {Question.objects.count()} questions, "
            f"{Option.objects.count()} options, {Attempt.objects.filter(submitted_at__isnull=False).count()} graded attempts."
        ))
