"""Seed BlogPress with demo authors, categories, posts and comments."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from core.models import Category, Comment, Post

CATEGORIES = [
    ("Engineering", "Deep dives into how we build."),
    ("Product", "Decisions, trade-offs and roadmaps."),
    ("Career", "Growth, interviews and teams."),
    ("Tutorials", "Step-by-step walkthroughs."),
]

POSTS = [
    ("ayesha", "Engineering", "Why we moved 40 services to Django 5.2", "🚀", True,
     "The migration took six weeks. Here is exactly what broke, what got faster, and the checklist we wish we had on day one.",
     "We run forty backend services. Half of them were on an aging framework branch, the other half on two different LTS lines.\n\n"
     "The trigger was boring: a security advisory landed on a Friday and patching three branches by hand was clearly unsustainable.\n\n"
     "Step one was inventory. We wrote a script that walked every repository, parsed the requirements files and produced a table of "
     "framework versions, database drivers and third-party packages.\n\n"
     "Step two was the boring-but-critical part: upgrading each service on its own branch, running the full test suite, and gating merges "
     "on a reproducible environment. No shared 'big bang' branch.\n\n"
     "The lesson: migrations are a process problem far more than a code problem. Version pinning, CI and review discipline did more for "
     "us than any clever sed command."),
    ("ayesha", "Tutorials", "Server-rendered forms that feel instant", "⚡", False,
     "You do not need a JavaScript framework to build a snappy interface. You need HTMX discipline and fast queries.",
     "Every team eventually asks: do we need a SPA? Usually the honest answer is no.\n\n"
     "Start by measuring. Most 'slow' pages are slow because of N+1 queries, not because of a full page reload.\n\n"
     "Our recipe: server-rendered templates, htmx for the three interactions that genuinely benefit, and a hard budget of under one "
     "second to first byte.\n\n"
     "The result is a codebase juniors can read on day one and a product that feels fast on a mid-range Android phone over 3G."),
    ("rafi", "Product", "The roadmap meeting that saved us six months", "🧭", True,
     "We cancelled half our roadmap. Revenue went up. Here is how we decided what to cut.",
     "We had fourteen items on the roadmap and four engineers. The maths never worked, but nobody said it out loud.\n\n"
     "So we ran an experiment: every item had to name the customer problem it solved and the metric it moved. Items that could not "
     "name both were removed for one quarter.\n\n"
     "Seven items died that afternoon. The remaining seven shipped on time.\n\n"
     "Cutting scope is not failure. Shipping the wrong thing quickly is."),
    ("rafi", "Career", "Hiring Django engineers: what we actually test", "🎯", False,
     "No whiteboard algorithms. Here is the four-hour take-home we use instead.",
     "We used to ask candidates to reverse a linked list. Then we noticed the correlation between that and job performance was close "
     "to zero.\n\n"
     "Now we give a small Django project with deliberately planted problems: an N+1 query, a missing ownership check, a form that "
     "trusts the client.\n\n"
     "Candidates have four hours, full documentation and an internet connection — exactly like the job.\n\n"
     "The best submissions do not just fix the bugs; they explain the trade-offs in the pull request description."),
    ("nadia", "Engineering", "Stop trusting the client: a security checklist", "🔒", True,
     "Six checks that would have caught most of the vulnerabilities we reviewed last year.",
     "Every vulnerability we reviewed last year traced back to the same root cause: trusting input from the browser.\n\n"
     "One: every mutation is a POST with a CSRF token. Two: ownership filters live in the query, not the template. Three: uploads are "
     "type- and size-checked server-side.\n\n"
     "Four: money is Decimal, never float. Five: rate limits on authentication. Six: CSP with a per-request nonce.\n\n"
     "None of this is exotic. It is just discipline applied consistently."),
    ("nadia", "Tutorials", "Database indexes: the three you actually need", "🗂️", False,
     "Most projects need far fewer indexes than they create. Start here.",
     "An index is a promise you make to the query planner. Like most promises, unkept ones are expensive.\n\n"
     "The three that earn their keep in nearly every app: the foreign key you filter by, the timestamp you sort by, and the composite "
     "of the two when you paginate.\n\n"
     "Everything else should be justified with an EXPLAIN plan and a real query pattern."),
    ("ayesha", "Tutorials", "Testing Django: the 20% that finds 80% of bugs", "🧪", False,
     "You do not need 100% coverage. You need these five test shapes.",
     "Coverage percentage is a vanity metric. Bug-catching rate is the real one.\n\n"
     "Five shapes that pay for themselves: permission boundaries (can user B touch user A's row?), state transitions (does publishing "
     "set a timestamp?), money maths, upload validation, and the seeder (does the demo actually load?).\n\n"
     "Write those first. Add more when a bug escapes to production."),
]


class Command(BaseCommand):
    help = "Create demo authors, categories, posts and comments."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for username, staff in [("ayesha", False), ("rafi", False), ("nadia", False), ("admin", True)]:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"email": f"{username}@blogpress.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = user.is_superuser = True
            user.save()

        for name, description in CATEGORIES:
            Category.objects.get_or_create(name=name, defaults={"description": description})

        now = timezone.now()
        for i, (author_name, cat_name, title, emoji, featured, excerpt, body) in enumerate(POSTS):
            author = User.objects.get(username=author_name)
            category = Category.objects.get(name=cat_name)
            post, created = Post.objects.get_or_create(
                title=title,
                defaults={
                    "author": author, "category": category, "excerpt": excerpt, "body": body,
                    "cover_emoji": emoji, "featured": featured, "status": Post.Status.PUBLISHED,
                    "published_at": now - timedelta(days=i * 3 + 1),
                    "views_count": 40 + i * 37,
                },
            )
            if created:
                reader = User.objects.get(username="rafi" if author_name != "rafi" else "ayesha")
                Comment.objects.create(post=post, author=reader, approved=True,
                                       body="This matches our experience exactly. Bookmarked.")
                if i % 3 == 0:
                    Comment.objects.create(post=post, author=reader, approved=False,
                                           body="Pending comment waiting for author moderation.")

        # One deliberate draft for the dashboard demo
        ayesha = User.objects.get(username="ayesha")
        Post.objects.get_or_create(
            title="Draft: what we learned rewriting the billing engine",
            defaults={"author": ayesha, "status": Post.Status.DRAFT, "cover_emoji": "📝",
                      "body": "Work in progress — not published yet. " * 6},
        )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Category.objects.count()} categories, {Post.objects.count()} posts, "
            f"{Comment.objects.count()} comments."
        ))
