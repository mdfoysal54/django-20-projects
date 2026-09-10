"""Seed LearnHub with demo instructors, courses, lessons, students and progress."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Course, Enrollment, Lesson, LessonProgress

COURSES = [
    {
        "title": "Django for Absolute Beginners",
        "instructor": "sara",
        "level": Course.Level.BEGINNER,
        "price": "0.00",
        "summary": "Go from zero to a working Django app in one weekend.",
        "description": (
            "Start with the request/response cycle, build your first models and views, "
            "add templates and ship a small but complete web app. No prior Django needed."
        ),
        "lessons": [
            ("Why Django? The big picture", 12, "What Django is, how MTV maps to MVC, and when to choose it."),
            ("Your first view and URL", 18, "Routing, view functions and the development server loop."),
            ("Models, migrations and the ORM", 26, "Define models, run makemigrations/migrate and query data."),
            ("Templates and static files", 22, "Render templates, extend a base layout and serve CSS."),
            ("Forms and validation", 24, "Django forms, CSRF protection and validation errors."),
            ("Deploy checklist", 15, "DEBUG=False, secrets in environment variables and static files."),
        ],
    },
    {
        "title": "Full-Stack Django: Build a SaaS",
        "instructor": "sara",
        "level": Course.Level.INTERMEDIATE,
        "price": "59.00",
        "summary": "Auth, billing concepts, background jobs and a real dashboard.",
        "description": (
            "Extend Django beyond the tutorial: custom user profiles, permissions, "
            "background tasks, caching and a production-ready deployment pipeline."
        ),
        "lessons": [
            ("Project architecture", 20, "Apps, services and settings layering."),
            ("Auth, permissions and sessions", 30, "Custom user model, groups and object-level checks."),
            ("Background jobs with Celery", 28, "Queues, retries and idempotent tasks."),
            ("Caching and performance", 24, "select_related, prefetch_related and cache invalidation."),
            ("Payments and webhooks (concepts)", 26, "Idempotency keys, webhook signatures and audit trails."),
            ("Observability and going live", 22, "Logging, health checks and zero-downtime deploys."),
        ],
    },
    {
        "title": "Django REST APIs Done Right",
        "instructor": "rafiq",
        "level": Course.Level.INTERMEDIATE,
        "price": "45.00",
        "summary": "Design REST APIs that are secure, versioned and a joy to consume.",
        "description": (
            "Serializers, viewsets, pagination, throttling, token/JWT auth and "
            "API-first design patterns with real-world examples."
        ),
        "lessons": [
            ("REST design principles", 18, "Resources, verbs, status codes and versioning."),
            ("Serializers and validation", 25, "Read/write serializers and nested data."),
            ("Views, routers and pagination", 27, "ViewSets, routers and cursor pagination."),
            ("Authentication and throttling", 29, "JWT, scopes and rate limits."),
            ("Testing the API", 23, "APIClient, factory data and contract tests."),
        ],
    },
    {
        "title": "Database Design for Developers",
        "instructor": "rafiq",
        "level": Course.Level.ADVANCED,
        "price": "39.00",
        "summary": "Model data the way senior engineers do — constraints, indexes, normal forms.",
        "description": (
            "From ER diagrams to migrations at scale: normalisation, indexes, "
            "transaction isolation levels and how to avoid the classic N+1 trap."
        ),
        "lessons": [
            ("Entities, relationships and keys", 22, "One-to-many, many-to-many and join tables."),
            ("Normalisation without dogma", 25, "When to normalise, when to denormalise deliberately."),
            ("Constraints as documentation", 20, "Unique, check and foreign-key constraints."),
            ("Indexes and query plans", 30, "EXPLAIN, composite indexes and covering indexes."),
            ("Transactions and isolation", 28, "ACID, lock modes and deadlock avoidance."),
            ("Scaling reads and writes", 26, "Replicas, sharding and when NOT to scale yet."),
        ],
    },
    {
        "title": "Web Security for Python Developers",
        "instructor": "sara",
        "level": Course.Level.ADVANCED,
        "price": "49.00",
        "summary": "OWASP Top 10, CSRF, XSS, SQLi and the Django defences against each.",
        "description": (
            "Understand the attacks your Django app faces and the specific framework "
            "features — CSP, ORM escaping, CSRF tokens — that neutralise them."
        ),
        "lessons": [
            ("The attacker's mindset", 16, "Threat models and the OWASP Top 10."),
            ("Injection and the ORM", 24, "SQLi, command injection and why raw SQL is risky."),
            ("XSS and Content-Security-Policy", 26, "Escaping, nonces and safe templates."),
            ("CSRF, sessions and cookies", 22, "Tokens, SameSite and fixation resistance."),
            ("Auth, hashing and rate limiting", 25, "Argon2, lockouts and credential stuffing."),
            ("Shipping securely", 18, "Deployment checklists and security headers."),
        ],
    },
    {
        "title": "Testing Django Like a Pro",
        "instructor": "rafiq",
        "level": Course.Level.INTERMEDIATE,
        "price": "35.00",
        "summary": "Test suites that catch real bugs — and stay fast as you grow.",
        "description": (
            "Unit vs integration vs end-to-end, factories, mocking, coverage goals "
            "and the tests every Django project should have on day one."
        ),
        "lessons": [
            ("What deserves a test?", 15, "Risk-based testing and the test pyramid."),
            ("TestCase, Client and fixtures", 24, "Unit and integration testing basics."),
            ("Factories and clean test data", 22, "Building realistic objects fast."),
            ("Testing auth and permissions", 20, "Login flows and object-level permissions."),
            ("Mocking external services", 21, "Freezing time and faking HTTP."),
            ("CI and coverage discipline", 17, "Running tests on every push."),
        ],
    },
]


class Command(BaseCommand):
    help = "Create demo instructors, courses, lessons and a student with progress."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for username, email, first in [("sara", "sara@learnhub.dev", "Sara"),
                                       ("rafiq", "rafiq@learnhub.dev", "Rafiq"),
                                       ("admin", "admin@learnhub.dev", "Admin")]:
            user, created = User.objects.get_or_create(username=username, defaults={"email": email})
            if created:
                user.set_password("DemoPass123!")
            if username == "admin":
                user.is_staff = user.is_superuser = True
            user.first_name = first
            user.save()

        for spec in COURSES:
            instructor = User.objects.get(username=spec["instructor"])
            course, created = Course.objects.get_or_create(
                title=spec["title"],
                defaults={
                    "instructor": instructor,
                    "level": spec["level"],
                    "price": Decimal(spec["price"]),
                    "summary": spec["summary"],
                    "description": spec["description"],
                    "status": Course.Status.PUBLISHED,
                },
            )
            if created:
                for order, (title, minutes, body) in enumerate(spec["lessons"], start=1):
                    Lesson.objects.create(
                        course=course, order=order, title=title,
                        duration_minutes=minutes, content=body,
                    )

        # Demo students with partial progress
        for username, course_titles, completed in [
            ("alice", ["Django for Absolute Beginners"], 3),
            ("bob", ["Django REST APIs Done Right", "Testing Django Like a Pro"], 2),
        ]:
            student, created = User.objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                student.set_password("DemoPass123!")
                student.save()
            for title in course_titles:
                course = Course.objects.filter(title=title).first()
                if not course:
                    continue
                enrollment, _ = Enrollment.objects.get_or_create(student=student, course=course)
                for lesson in list(course.lessons)[:completed]:
                    LessonProgress.objects.get_or_create(
                        enrollment=enrollment, lesson=lesson, defaults={"completed": True},
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Course.objects.count()} courses, {Lesson.objects.count()} lessons, "
            f"{Enrollment.objects.count()} enrolments."
        ))
