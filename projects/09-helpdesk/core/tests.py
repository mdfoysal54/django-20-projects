"""HelpDesk domain tests — visibility, the status machine, SLA and triage rules."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Department, Feedback, Ticket, TicketEvent, TicketMessage


def make_ticket(requester, status=Ticket.Status.OPEN, priority=Ticket.Priority.NORMAL, subject="Login page loops"):
    return Ticket.objects.create(requester=requester, subject=subject, body="Detailed description of the problem.",
                                 department=Department.objects.get_or_create(name="Support")[0],
                                 status=status, priority=priority)


class VisibilityTests(TestCase):
    """The core promise: you see your tickets, agents see everything, notes stay internal."""

    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.bob = User.objects.create_user("bob", password="Str0ng!Passw0rd")
        self.agent = User.objects.create_user("agent", password="Str0ng!Passw0rd", is_staff=True)
        self.ticket = make_ticket(self.alice, subject="Alice cannot log in")

    def test_requester_sees_own_ticket(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ticket.reference)

    def test_stranger_gets_404_not_403(self):
        self.client.force_login(self.bob)
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 404)      # existence is not leaked

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_agent_sees_any_ticket(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(self.ticket.get_absolute_url()).status_code, 200)

    def test_my_tickets_list_is_scoped(self):
        make_ticket(self.bob, subject="Bob problem entirely different")
        self.client.force_login(self.alice)
        response = self.client.get(reverse("my_tickets"))
        self.assertContains(response, "Alice cannot log in")
        self.assertNotContains(response, "Bob problem")


class InternalNoteTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.agent = User.objects.create_user("agent", password="Str0ng!Passw0rd", is_staff=True)
        self.ticket = make_ticket(self.alice)
        self.ticket.add_message(self.agent, "Customer is on the legacy auth cluster.", internal=True)
        self.ticket.add_message(self.agent, "We are on it — reset link sent.", internal=False)

    def test_requester_never_sees_internal_notes(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertContains(response, "reset link sent")
        self.assertNotContains(response, "legacy auth cluster")

    def test_agent_sees_internal_notes(self):
        self.client.force_login(self.agent)
        response = self.client.get(self.ticket.get_absolute_url())
        self.assertContains(response, "legacy auth cluster")

    def test_requester_cannot_forge_an_internal_note_field(self):
        """Even if the hidden field is posted by hand, it is ignored."""
        self.client.force_login(self.alice)
        self.client.post(self.ticket.get_absolute_url(),
                         {"action": "reply", "body": "Trying to mark this internal.", "internal": "on"})
        message = TicketMessage.objects.filter(author=self.alice).latest("created")
        self.assertFalse(message.internal)


class StatusMachineTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.agent = User.objects.create_user("agent", password="Str0ng!Passw0rd", is_staff=True)
        self.ticket = make_ticket(self.alice)

    def test_legal_flow_open_to_resolved(self):
        self.ticket.set_status(Ticket.Status.IN_PROGRESS, self.agent)
        self.ticket.set_status(Ticket.Status.RESOLVED, self.agent)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.RESOLVED)
        self.assertIsNotNone(self.ticket.resolved_at)

    def test_same_status_is_a_noop(self):
        self.ticket.set_status(Ticket.Status.OPEN, self.agent)
        self.assertEqual(self.ticket.events.count(), 0)    # no spurious audit rows

    def test_resolving_clears_resolved_at_when_reopened(self):
        self.ticket.set_status(Ticket.Status.RESOLVED, self.agent)
        self.ticket.set_status(Ticket.Status.OPEN, self.agent)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.resolved_at)

    def test_illegal_transition_raises_and_is_not_saved(self):
        self.ticket.status = Ticket.Status.OPEN
        with self.assertRaises(ValueError):
            self.ticket.set_status("banana", self.agent)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.OPEN)

    def test_agent_view_rejects_illegal_status(self):
        self.client.force_login(self.agent)
        response = self.client.post(self.ticket.get_absolute_url(),
                                    {"action": "triage", "priority": "normal",
                                     "status": "resolved", "assignee": ""}, follow=True)
        self.assertContains(response, "Resolved")          # legal move applied
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.RESOLVED)

    def test_customer_cannot_change_status(self):
        self.client.force_login(self.alice)
        self.client.post(self.ticket.get_absolute_url(),
                         {"action": "triage", "priority": "urgent", "status": "closed"})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.OPEN)
        self.assertEqual(self.ticket.priority, Ticket.Priority.NORMAL)   # not escalated

    def test_requester_can_reopen_resolved_ticket(self):
        self.ticket.set_status(Ticket.Status.RESOLVED, self.agent)
        self.client.force_login(self.alice)
        self.client.post(self.ticket.get_absolute_url(), {"action": "reopen"})
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.OPEN)


class TriageAndSlaTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.agent = User.objects.create_user("agent", password="Str0ng!Passw0rd", is_staff=True)
        self.agent2 = User.objects.create_user("agent2", password="Str0ng!Passw0rd", is_staff=True)
        self.ticket = make_ticket(self.alice)

    def test_queue_is_agent_only(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("queue"))
        self.assertEqual(response.status_code, 302)       # bounced to login
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("queue")).status_code, 200)

    def test_metrics_is_agent_only(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 302)

    def test_claim_sets_assignee_and_moves_to_in_progress(self):
        self.client.force_login(self.agent)
        self.client.post(reverse("claim", kwargs={"reference": self.ticket.reference}))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assignee, self.agent)
        self.assertEqual(self.ticket.status, Ticket.Status.IN_PROGRESS)

    def test_second_agent_cannot_steal_a_claimed_ticket(self):
        self.client.force_login(self.agent)
        self.client.post(reverse("claim", kwargs={"reference": self.ticket.reference}))
        self.client.force_login(self.agent2)
        self.client.post(reverse("claim", kwargs={"reference": self.ticket.reference}))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assignee, self.agent)     # unchanged

    def test_sla_deadline_depends_on_priority(self):
        self.ticket.set_priority(Ticket.Priority.URGENT, self.agent)
        hours = (self.ticket.sla_due - timezone.now()).total_seconds() / 3600
        self.assertAlmostEqual(hours, 4, delta=0.2)
        self.ticket.set_priority(Ticket.Priority.LOW, self.agent)
        hours = (self.ticket.sla_due - timezone.now()).total_seconds() / 3600
        self.assertAlmostEqual(hours, 72, delta=0.2)

    def test_first_response_recorded_on_agent_reply(self):
        self.assertIsNone(self.ticket.first_response_at)
        self.ticket.add_message(self.agent, "Looking into it now.")
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.first_response_at)
        self.assertIsNotNone(self.ticket.minutes_to_first_response)

    def test_internal_note_does_not_count_as_first_response(self):
        self.ticket.add_message(self.agent, "note to self", internal=True)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.first_response_at)

    def test_breached_when_past_deadline_without_reply(self):
        Ticket.objects.filter(pk=self.ticket.pk).update(
            sla_due=timezone.now() - timedelta(hours=1))
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_breached)
        self.ticket.add_message(self.agent, "Sorry for the wait!")
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.is_breached)           # late reply is still a breach

    def test_audit_trail_records_changes(self):
        self.ticket.assign_to(self.agent)
        self.ticket.set_priority(Ticket.Priority.HIGH, self.agent)
        kinds = list(self.ticket.events.values_list("kind", flat=True))
        self.assertIn("assigned", kinds)
        self.assertIn("priority", kinds)


class FeedbackTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Str0ng!Passw0rd")
        self.bob = User.objects.create_user("bob", password="Str0ng!Passw0rd")
        self.agent = User.objects.create_user("agent", password="Str0ng!Passw0rd", is_staff=True)
        self.ticket = make_ticket(self.alice)
        self.ticket.set_status(Ticket.Status.RESOLVED, self.agent)

    def test_only_resolved_tickets_can_be_rated(self):
        other = make_ticket(self.alice, subject="Still open issue here")
        self.client.force_login(self.alice)
        self.client.post(reverse("give_feedback", kwargs={"reference": other.reference}), {"score": 5})
        self.assertFalse(Feedback.objects.filter(ticket=other).exists())

    def test_rating_saved_and_updated_once(self):
        self.client.force_login(self.alice)
        url = reverse("give_feedback", kwargs={"reference": self.ticket.reference})
        self.client.post(url, {"score": 4, "comment": "Quick fix."})
        self.client.post(url, {"score": 5, "comment": "Even better."})
        self.assertEqual(Feedback.objects.filter(ticket=self.ticket).count(), 1)
        self.assertEqual(Feedback.objects.get(ticket=self.ticket).score, 5)

    def test_stranger_cannot_rate_someone_elses_ticket(self):
        self.client.force_login(self.bob)
        response = self.client.post(reverse("give_feedback", kwargs={"reference": self.ticket.reference}), {"score": 1})
        self.assertEqual(response.status_code, 404)


class SeederTests(TestCase):
    def test_seed_demo_populates_desk(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Department.objects.count(), 3)
        self.assertGreaterEqual(Ticket.objects.count(), 8)
        self.assertTrue(TicketMessage.objects.filter(internal=True).exists())
        self.assertTrue(Ticket.objects.filter(assignee__isnull=True).exists())
        self.assertTrue(Feedback.objects.exists())
        self.assertTrue(TicketEvent.objects.exists())
