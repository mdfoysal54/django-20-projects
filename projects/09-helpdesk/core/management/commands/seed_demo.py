"""Seed HelpDesk with departments, agents, tickets, threads and feedback."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Department, Feedback, Ticket, TicketEvent, TicketMessage

DEPARTMENTS = [
    ("Billing", "billing", "💳", "Invoices, refunds and payment failures."),
    ("Technical", "technical", "🛠️", "Bugs, outages and integration problems."),
    ("Accounts", "accounts", "🔑", "Logins, permissions and password resets."),
    ("Shipping", "shipping", "📦", "Delivery tracking and lost parcels."),
]

TICKETS = [
    ("billing", "Charged twice for August subscription", "high", "open", None,
     "Our card was charged twice on August 3rd. Invoice INV-2231 shows one payment, the bank shows two. We need the duplicate refunded.",
     [("agent", "I can see both authorisations on the gateway. Raising a refund now.", False),
      ("agent", "Gateway refund window closes in 48h — escalate if not settled.", True)]),
    ("technical", "Exports time out on large accounts", "urgent", "in_progress", "agent",
     "CSV export fails with a 504 for any account with more than 50k rows. Started after Tuesday's deploy. Blocking month-end reporting.",
     [("agent", "Confirmed: the query is doing a full table scan. Patch is in review.", False),
      ("customer", "Thanks — any ETA? Month-end close is on Friday.", False)]),
    ("accounts", "Password reset email never arrives", "normal", "resolved", "agent2",
     "Reset link never arrives for our whole domain, not just me. Works for personal Gmail accounts.",
     [("agent2", "Your mail filter was quarantining our sender. Allowlisted.", False),
      ("customer", "Confirmed working, thanks!", False)]),
    ("shipping", "Parcel marked delivered but never arrived", "high", "waiting", "agent2",
     "Tracking says delivered Tuesday 14:20 but nothing arrived. Building has a signed reception.",
     [("agent2", "Courier is checking the driver's route photos. Asking you to hold.", False)]),
    ("technical", "API returns 429 during nightly batch", "normal", "open", None,
     "Our nightly sync hits the rate limit at around 02:00 every day. We are well under our documented quota.",
     []),
    ("billing", "VAT number missing from invoices", "low", "open", None,
     "Our finance team needs our VAT number printed on every invoice for compliance. Currently absent.",
     []),
    ("accounts", "SSO login loops back to sign-in page", "urgent", "in_progress", "agent",
     "Azure AD SSO redirects to the dashboard then straight back to login. Affects 40 users, all hands blocked.",
     [("agent", "Clock skew on the IdP — 4 minutes. Coordinating with your IT.", True)]),
    ("shipping", "Change delivery address on open order", "normal", "open", None,
     "We moved offices last week and the order still points at the old address. Can it be redirected?",
     []),
]

CUSTOMERS = [("customer", "customer@client.dev"), ("customer2", "ops@client.dev"), ("customer3", "it@client.dev")]


class Command(BaseCommand):
    help = "Create demo departments, agents, customers, tickets and threads."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG=False.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed demo data with DEBUG=False. Pass --force."))
            return

        for username, staff in [("agent", True), ("agent2", True), ("admin", True)] + \
                               [(u, False) for u, _ in CUSTOMERS]:
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@helpdesk.dev"})
            if created:
                user.set_password("DemoPass123!")
            if staff:
                user.is_staff = True
            user.save()
        User.objects.filter(username="admin").update(is_superuser=True)

        for name, slug, emoji, description in DEPARTMENTS:
            Department.objects.get_or_create(name=name, defaults={"slug": slug, "emoji": emoji,
                                                                  "description": description})

        now = timezone.now()
        for i, (dept_slug, subject, priority, status, assignee_name, body, thread) in enumerate(TICKETS):
            department = Department.objects.get(slug=dept_slug)
            requester = User.objects.get(username=CUSTOMERS[i % len(CUSTOMERS)][0])
            ticket, created = Ticket.objects.get_or_create(
                subject=subject,
                defaults={
                    "requester": requester, "department": department, "body": body,
                    "priority": priority, "status": status,
                    "assignee": User.objects.get(username=assignee_name) if assignee_name else None,
                },
            )
            if not created:
                continue
            # Back-date so the SLA panel has interesting data.
            created_at = now - timedelta(hours=6 + i * 5)
            Ticket.objects.filter(pk=ticket.pk).update(created=created_at,
                                                       sla_due=created_at + timedelta(
                                                           hours=Ticket.SLA_HOURS[ticket.priority]))
            TicketEvent.objects.create(ticket=ticket, actor=requester, kind="created",
                                       detail=f"Ticket opened in {department.name}")
            for author_name, text, internal in thread:
                author = User.objects.get(username=author_name)
                TicketMessage.objects.create(ticket=ticket, author=author, body=text, internal=internal)
                if not internal and author.is_staff:
                    Ticket.objects.filter(pk=ticket.pk, first_response_at__isnull=True).update(
                        first_response_at=created_at + timedelta(hours=2))
            if status == "resolved":
                Ticket.objects.filter(pk=ticket.pk).update(resolved_at=now - timedelta(hours=1))
                Feedback.objects.get_or_create(ticket=ticket, defaults={"score": 5,
                                                                        "comment": "Fast and clear."})

        # One closed ticket with a mediocre score, for the CSAT panel.
        dept = Department.objects.get(slug="accounts")
        requester = User.objects.get(username="customer2")
        closed = Ticket.objects.create(
            requester=requester, department=dept, subject="Two-factor codes delayed by minutes",
            body="2FA codes arrive after the 60-second window has expired, so login always takes two tries.",
            priority="normal", status="closed", assignee=User.objects.get(username="agent2"),
        )
        TicketMessage.objects.create(ticket=closed, author=User.objects.get(username="agent2"),
                                     body="Carrier delays on short codes. Switched you to authenticator app.",
                                     internal=False)
        Ticket.objects.filter(pk=closed.pk).update(first_response_at=timezone.now() - timedelta(hours=3),
                                                    resolved_at=timezone.now() - timedelta(hours=2))
        Feedback.objects.create(ticket=closed, score=3, comment="Took longer than hoped.")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Department.objects.count()} departments, {Ticket.objects.count()} tickets, "
            f"{TicketMessage.objects.count()} messages, {Feedback.objects.count()} ratings."
        ))
