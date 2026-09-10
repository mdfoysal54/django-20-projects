"""Seed DevJobs with demo companies, jobs and applications."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Application, Company, Job

COMPANIES = [
    {
        "name": "Nimbus Cloud", "emoji": "☁️", "location": "Dhaka, Bangladesh",
        "website": "https://nimbus-cloud.example.com",
        "about": "Cloud infrastructure platform serving 40k developers across South Asia.",
        "jobs": [
            {
                "title": "Senior Django Engineer", "level": Job.Level.SENIOR, "remote": Job.Remote.HYBRID,
                "location": "Dhaka (hybrid)", "salary": (6000, 9500), "tags": "Django, PostgreSQL, Celery, Redis",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Own the backbone of our API platform: multi-tenant Django services handling "
                    "millions of requests a day. You will design data models, tune queries, and help "
                    "junior engineers level up through reviews."
                ),
                "requirements": "5+ years Python\nExpert-level Django ORM\nPostgreSQL performance tuning\nExperience with Celery/Redis\nStrong written English",
            },
            {
                "title": "Frontend Engineer (HTMX + Django)", "level": Job.Level.MID, "remote": Job.Remote.REMOTE,
                "location": "Remote (GMT+6 ±3)", "salary": (3000, 5000), "tags": "HTMX, Alpine.js, CSS, Django",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Build server-rendered interfaces that feel instant. We ship HTMX-first product "
                    "surfaces and care deeply about accessibility and page weight budgets."
                ),
                "requirements": "3+ years frontend\nStrong CSS fundamentals\nHTMX or similar\nEye for accessibility",
            },
            {
                "title": "Platform Intern", "level": Job.Level.JUNIOR, "remote": Job.Remote.ONSITE,
                "location": "Dhaka (on-site)", "salary": (350, 450), "tags": "Linux, Docker, CI/CD, Python",
                "type": Job.Type.INTERNSHIP,
                "description": (
                    "Six-month paid internship on our platform team: container builds, CI pipelines, "
                    "monitoring dashboards. Mentored weekly with a clear path to full-time."
                ),
                "requirements": "CS student or recent grad\nBasic Linux/Docker\nScripting in Python or Bash",
            },
        ],
    },
    {
        "name": "Pixel & Pine", "emoji": "🌲", "location": "Chattogram, Bangladesh",
        "website": "https://pixelpine.example.com",
        "about": "Digital product studio crafting e-commerce storefronts for regional brands.",
        "jobs": [
            {
                "title": "Django Developer — E-commerce", "level": Job.Level.MID, "remote": Job.Remote.ONSITE,
                "location": "Chattogram", "salary": (2500, 4000), "tags": "Django, Stripe, Wagtail, Docker",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Help us rebuild storefronts for three national retail brands. Work spans "
                    "catalogues, payments integration concepts and CMS-driven content."
                ),
                "requirements": "3+ years Django\nE-commerce domain knowledge\nDRF basics\nGit discipline",
            },
            {
                "title": "Technical Project Manager", "level": Job.Level.LEAD, "remote": Job.Remote.HYBRID,
                "location": "Chattogram (hybrid)", "salary": (3500, 5200), "tags": "Agile, Scrum, Stakeholders",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Run three parallel client builds: scope, schedule and shield the team. "
                    "You will be the bridge between clients and engineers, with real authority to say no."
                ),
                "requirements": "5+ years managing software projects\nScrum fluency\nTechnical enough to argue with engineers (kindly)",
            },
        ],
    },
    {
        "name": "BlueOrbit Labs", "emoji": "🛰️", "location": "Remote-first",
        "website": "https://blueorbit.example.com",
        "about": "Data platform for satellite imagery processing. Fully remote, 14 countries.",
        "jobs": [
            {
                "title": "Backend Engineer — Geospatial", "level": Job.Level.SENIOR, "remote": Job.Remote.REMOTE,
                "location": "Remote (worldwide)", "salary": (7000, 11000), "tags": "Python, GDAL, PostGIS, Django",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Process terabytes of imagery into tiles our customers can query in milliseconds. "
                    "Heavy PostGIS work, pipeline design, and performance engineering."
                ),
                "requirements": "Geospatial data experience\nPostGIS or equivalent\nPython pipelines at scale\nAsync processing",
            },
            {
                "title": "DevOps Engineer", "level": Job.Level.SENIOR, "remote": Job.Remote.REMOTE,
                "location": "Remote (worldwide)", "salary": (6500, 10000), "tags": "Kubernetes, Terraform, AWS, Python",
                "type": Job.Type.CONTRACT,
                "description": (
                    "Own our Kubernetes footprint and infrastructure-as-code. Six-month contract with "
                    "extension potential; you set your own hours within overlap windows."
                ),
                "requirements": "Kubernetes in production\nTerraform or Pulumi\nCost optimisation instinct\nOn-call maturity",
            },
        ],
    },
    {
        "name": "The Ledger Co", "emoji": "💹", "location": "Dhaka, Bangladesh",
        "website": "https://ledgerco.example.com",
        "about": "Fintech startup building SME accounting tools for Bangladesh.",
        "jobs": [
            {
                "title": "Junior Python Developer", "level": Job.Level.JUNIOR, "remote": Job.Remote.HYBRID,
                "location": "Dhaka (hybrid)", "salary": (1200, 1800), "tags": "Python, Django, SQL, Git",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Your first real job, done right: pair programming, reviewed PRs, and a mentor who "
                    "explains the why. You will ship to production in your first month."
                ),
                "requirements": "CS fundamentals\nA Django project you can show\nWillingness to learn fast",
            },
            {
                "title": "QA Engineer", "level": Job.Level.MID, "remote": Job.Remote.ONSITE,
                "location": "Dhaka", "salary": (1500, 2400), "tags": "Selenium, Pytest, API Testing",
                "type": Job.Type.FULL_TIME,
                "description": (
                    "Build the test discipline of a fintech: API test suites, regression automation, "
                    "and release checklists that regulators will love."
                ),
                "requirements": "Pytest or similar\nAPI testing experience\nDetail obsession",
            },
        ],
    },
]

APPLICATIONS = [
    ("alice", "Senior Django Engineer", "I have led Django teams for seven years and once cut a query from 40s to 80ms.", Application.Status.INTERVIEW),
    ("alice", "Backend Engineer — Geospatial", "PostGIS power user; I maintain an open-source tile server.", Application.Status.SHORTLISTED),
    ("bob", "Junior Python Developer", "Final-year CS student; built a library system in Django as coursework.", Application.Status.SUBMITTED),
    ("bob", "Frontend Engineer (HTMX + Django)", "I love HTMX and ship accessible interfaces.", Application.Status.REVIEWING),
]


class Command(BaseCommand):
    help = "Create demo companies, jobs, candidates and applications."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        admin, created = User.objects.get_or_create(username="admin", defaults={"email": "admin@devjobs.dev"})
        if created:
            admin.set_password("DemoPass123!")
        admin.is_staff = admin.is_superuser = True
        admin.save()

        recruiters = {}
        for username in ("nadia", "tanvir"):
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@devjobs.dev"})
            if created:
                user.set_password("DemoPass123!")
                user.save()
            recruiters[username] = user

        recruiter_cycle = ["nadia", "tanvir"]
        for i, spec in enumerate(COMPANIES):
            recruiter = recruiters[recruiter_cycle[i % 2]]
            company, created = Company.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "owner": recruiter, "website": spec["website"],
                    "location": spec["location"], "about": spec["about"],
                    "logo_emoji": spec["emoji"],
                },
            )
            for job_spec in spec["jobs"]:
                salary = job_spec["salary"]
                Job.objects.get_or_create(
                    title=job_spec["title"], company=company,
                    defaults={
                        "posted_by": recruiter,
                        "description": job_spec["description"],
                        "requirements": job_spec["requirements"],
                        "location": job_spec["location"],
                        "remote": job_spec["remote"],
                        "job_type": job_spec["type"],
                        "level": job_spec["level"],
                        "salary_min": Decimal(str(salary[0])),
                        "salary_max": Decimal(str(salary[1])),
                        "tags": job_spec["tags"],
                        "status": Job.Status.OPEN,
                        "deadline": timezone.localdate() + timedelta(days=30 + i * 7),
                    },
                )

        for username in ("alice", "bob"):
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.com"})
            if created:
                user.set_password("DemoPass123!")
                user.save()

        for username, job_title, letter, status in APPLICATIONS:
            job = Job.objects.filter(title=job_title).first()
            user = User.objects.filter(username=username).first()
            if job and user:
                Application.objects.get_or_create(
                    job=job, applicant=user,
                    defaults={"cover_letter": letter, "status": status},
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Company.objects.count()} companies, {Job.objects.count()} jobs, "
            f"{Application.objects.count()} applications."
        ))
