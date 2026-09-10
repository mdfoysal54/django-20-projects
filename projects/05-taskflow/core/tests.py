"""TaskFlow domain tests — membership isolation, role matrix, board mechanics."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Activity, Comment, Membership, Project, Task


def make_project(owner, name="Project Alpha", **kw):
    return Project.objects.create(owner=owner, name=name, **kw)


def add_member(project, user, role=Membership.Role.MEMBER):
    return Membership.objects.create(project=project, user=user, role=role)


def make_task(project, creator, title="Do the thing", status=Task.Status.TODO, **kw):
    return Task.objects.create(project=project, created_by=creator, title=title, status=status, **kw)


class ProjectIsolationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.member = User.objects.create_user("member", password="Str0ng!Passw0rd")
        self.viewer = User.objects.create_user("viewer", password="Str0ng!Passw0rd")
        self.stranger = User.objects.create_user("stranger", password="Str0ng!Passw0rd")
        self.project = make_project(self.owner)
        add_member(self.project, self.member, Membership.Role.MEMBER)
        add_member(self.project, self.viewer, Membership.Role.VIEWER)

    def test_only_participants_can_view_project(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 200)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 200)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.project.get_absolute_url()).status_code, 200)

    def test_stranger_gets_404_not_403(self):
        """No existence leak: unrelated users cannot even tell the project exists."""
        self.client.force_login(self.stranger)
        response = self.client.get(self.project.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_dashboard_lists_only_my_projects(self):
        other_project = make_project(self.stranger, "Hidden Project")
        self.client.force_login(self.member)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Project Alpha")
        self.assertNotContains(response, "Hidden Project")
        _ = other_project

    def test_role_lookup(self):
        self.assertEqual(self.project.role_of(self.owner), "owner")
        self.assertEqual(self.project.role_of(self.member), "member")
        self.assertEqual(self.project.role_of(self.viewer), "viewer")
        self.assertIsNone(self.project.role_of(self.stranger))
        self.assertIsNone(self.project.role_of(None))


class RoleMatrixTests(TestCase):
    """viewer < member < admin: each role's exact powers, negative + positive."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.admin = User.objects.create_user("admin_user", password="Str0ng!Passw0rd")
        self.member = User.objects.create_user("member", password="Str0ng!Passw0rd")
        self.viewer = User.objects.create_user("viewer", password="Str0ng!Passw0rd")
        self.project = make_project(self.owner)
        add_member(self.project, self.admin, Membership.Role.ADMIN)
        add_member(self.project, self.member, Membership.Role.MEMBER)
        add_member(self.project, self.viewer, Membership.Role.VIEWER)

    def login(self, user):
        self.client.force_login(user)

    # ---- task creation ----------------------------------------------------
    def test_member_and_admin_can_create_tasks_viewer_cannot(self):
        for user, expected in [(self.member, 302), (self.admin, 302), (self.viewer, 403)]:
            self.login(user)
            response = self.client.post(
                reverse("task_create", kwargs={"slug": self.project.slug}),
                {"title": f"Task by {user.username}", "status": Task.Status.TODO,
                 "priority": Task.Priority.MEDIUM},
            )
            self.assertEqual(response.status_code, expected, user.username)
        # member + admin succeeded, viewer didn't
        self.assertEqual(Task.objects.count(), 2)

    # ---- comments ---------------------------------------------------------
    def test_viewer_cannot_comment(self):
        task = make_task(self.project, self.owner)
        self.login(self.viewer)
        response = self.client.post(reverse("task_detail", kwargs={"pk": task.pk}), {"body": "Looks good!"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.exists())

    def test_member_can_comment(self):
        task = make_task(self.project, self.owner)
        self.login(self.member)
        self.client.post(reverse("task_detail", kwargs={"pk": task.pk}), {"body": "On it."})
        self.assertEqual(Comment.objects.count(), 1)

    # ---- member management -------------------------------------------------
    def test_only_admin_and_owner_can_manage_members(self):
        newbie = User.objects.create_user("newbie", password="Str0ng!Passw0rd")
        self.login(self.member)
        response = self.client.post(
            reverse("member_list", kwargs={"slug": self.project.slug}),
            {"username": "newbie", "role": Membership.Role.MEMBER},
        )
        self.assertEqual(response.status_code, 403)   # member may not manage
        self.assertFalse(Membership.objects.filter(user=newbie).exists())

        self.login(self.admin)
        response = self.client.post(
            reverse("member_list", kwargs={"slug": self.project.slug}),
            {"username": "newbie", "role": Membership.Role.VIEWER},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Membership.objects.filter(project=self.project, user=newbie).exists())

    def test_project_edit_is_admin_plus(self):
        self.login(self.member)
        self.assertEqual(
            self.client.post(reverse("project_edit", kwargs={"slug": self.project.slug}),
                             {"name": "Hacked", "description": "", "color": "#000000"}).status_code,
            403,
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Project Alpha")

    def test_task_delete_is_admin_plus(self):
        task = make_task(self.project, self.owner)
        self.login(self.member)
        response = self.client.post(reverse("task_delete", kwargs={"slug": self.project.slug, "pk": task.pk}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

        self.login(self.admin)
        self.client.post(reverse("task_delete", kwargs={"slug": self.project.slug, "pk": task.pk}))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_owner_cannot_be_added_as_member(self):
        self.login(self.owner)
        response = self.client.post(
            reverse("member_list", kwargs={"slug": self.project.slug}),
            {"username": "owner", "role": Membership.Role.MEMBER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "owns this project")


class BoardTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.member = User.objects.create_user("member", password="Str0ng!Passw0rd")
        self.project = make_project(self.owner)
        add_member(self.project, self.member)
        self.client.force_login(self.member)

    def test_move_task_between_columns_sets_completed_at(self):
        task = make_task(self.project, self.owner)
        url = reverse("task_move", kwargs={"slug": self.project.slug, "pk": task.pk})
        self.client.post(url, {"status": Task.Status.IN_PROGRESS})
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
        self.assertIsNone(task.completed_at)

        self.client.post(url, {"status": Task.Status.DONE})
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.DONE)
        self.assertIsNotNone(task.completed_at)

        # Moving back out clears it again
        self.client.post(url, {"status": Task.Status.REVIEW})
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)

    def test_moves_are_logged_as_activity(self):
        task = make_task(self.project, self.owner)
        self.client.post(reverse("task_move", kwargs={"slug": self.project.slug, "pk": task.pk}),
                         {"status": Task.Status.REVIEW})
        self.assertEqual(Activity.objects.filter(project=self.project).count(), 1)

    def test_invalid_column_rejected(self):
        task = make_task(self.project, self.owner)
        self.client.post(reverse("task_move", kwargs={"slug": self.project.slug, "pk": task.pk}),
                         {"status": "nonsense"})
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.TODO)

    def test_reordering_swaps_positions(self):
        first = make_task(self.project, self.owner, title="First", position=1)
        second = make_task(self.project, self.owner, title="Second", position=2)
        self.client.post(
            reverse("task_move", kwargs={"slug": self.project.slug, "pk": second.pk}),
            {"status": second.status, "direction": "up"},
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertLess(second.position, first.position)

    def test_status_change_is_cross_project_safe(self):
        """A task pk from one project cannot be moved via another project's URL."""
        other_project = make_project(self.owner, "Other Project")
        foreign_task = make_task(other_project, self.owner, title="Foreign")
        response = self.client.post(
            reverse("task_move", kwargs={"slug": self.project.slug, "pk": foreign_task.pk}),
            {"status": Task.Status.DONE},
        )
        self.assertEqual(response.status_code, 404)
        foreign_task.refresh_from_db()
        self.assertEqual(foreign_task.status, Task.Status.TODO)

    def test_progress_maths(self):
        make_task(self.project, self.owner, status=Task.Status.DONE)
        make_task(self.project, self.owner, status=Task.Status.DONE)
        make_task(self.project, self.owner, status=Task.Status.TODO)
        self.assertEqual(self.project.task_count, 3)
        self.assertEqual(self.project.done_count, 2)
        self.assertEqual(self.project.progress_percent, 67)

    def test_due_states_and_overdue(self):
        overdue = make_task(self.project, self.owner, due_date=timezone.localdate() - timedelta(days=1))
        today = make_task(self.project, self.owner, due_date=timezone.localdate())
        later = make_task(self.project, self.owner, due_date=timezone.localdate() + timedelta(days=9))
        done = make_task(self.project, self.owner, status=Task.Status.DONE,
                         due_date=timezone.localdate() - timedelta(days=5))
        self.assertEqual(overdue.due_state, "overdue")
        self.assertTrue(overdue.is_overdue)
        self.assertEqual(today.due_state, "today")
        self.assertEqual(later.due_state, "later")
        self.assertEqual(done.due_state, "")          # done tasks never nag
        self.assertFalse(done.is_overdue)


class TaskFormTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="Str0ng!Passw0rd")
        self.member = User.objects.create_user("member", password="Str0ng!Passw0rd")
        self.outsider = User.objects.create_user("outsider", password="Str0ng!Passw0rd")
        self.project = make_project(self.owner)
        add_member(self.project, self.member)
        self.client.force_login(self.member)

    def test_assignee_must_be_project_participant(self):
        response = self.client.post(
            reverse("task_create", kwargs={"slug": self.project.slug}),
            {"title": "Sneaky assignment", "status": Task.Status.TODO,
             "priority": Task.Priority.MEDIUM, "assignee": self.outsider.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.exists())

    def test_assignee_can_be_owner(self):
        response = self.client.post(
            reverse("task_create", kwargs={"slug": self.project.slug}),
            {"title": "Assign to owner", "status": Task.Status.TODO,
             "priority": Task.Priority.MEDIUM, "assignee": self.owner.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Task.objects.get().assignee, self.owner)

    def test_short_title_rejected(self):
        response = self.client.post(
            reverse("task_create", kwargs={"slug": self.project.slug}),
            {"title": "ab", "status": Task.Status.TODO, "priority": Task.Priority.MEDIUM},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.exists())


class SeederTests(TestCase):
    def test_seed_demo_populates_workspace(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Project.objects.count(), 3)
        self.assertGreaterEqual(Task.objects.count(), 18)
        self.assertTrue(Comment.objects.exists())
        self.assertTrue(Activity.objects.exists())
        self.assertTrue(Membership.objects.exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
