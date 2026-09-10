"""BlogPress domain tests — visibility rules, moderation, author ownership."""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Category, Comment, Post


def make_post(author, title="A Fairly Long Title", status=Post.Status.PUBLISHED, **kw):
    return Post.objects.create(author=author, title=title, status=status,
                               body="Body text long enough to pass validation. " * 4, **kw)


class PublishFlowTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("writer", password="Str0ng!Passw0rd")
        self.draft = make_post(self.author, "Secret Draft", status=Post.Status.DRAFT)
        self.live = make_post(self.author, "Public Post")

    def test_only_published_posts_appear_publicly(self):
        response = self.client.get(reverse("post_list"))
        self.assertContains(response, "Public Post")
        self.assertNotContains(response, "Secret Draft")

    def test_draft_detail_is_404_for_everyone(self):
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)  # drafts have no public page

    def test_toggle_publish(self):
        self.client.force_login(self.author)
        self.client.post(reverse("post_toggle_publish", kwargs={"slug": self.draft.slug}))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(self.draft.published_at)
        self.client.post(reverse("post_toggle_publish", kwargs={"slug": self.draft.slug}))
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Post.Status.DRAFT)

    def test_view_counter_increments(self):
        self.assertEqual(self.live.views_count, 0)
        self.client.get(self.live.get_absolute_url())
        self.client.get(self.live.get_absolute_url())
        self.live.refresh_from_db()
        self.assertEqual(self.live.views_count, 2)

    def test_reading_time_is_sane(self):
        post = make_post(self.author, "Short One")
        self.assertGreaterEqual(post.reading_minutes, 1)


class AuthorOwnershipTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("writer", password="Str0ng!Passw0rd")
        self.other = User.objects.create_user("rival", password="Str0ng!Passw0rd")
        self.post = make_post(self.author, "Owned Post")

    def test_non_author_cannot_edit(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("post_edit", kwargs={"slug": self.post.slug}))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("post_toggle_publish", kwargs={"slug": self.post.slug}))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("post_delete", kwargs={"slug": self.post.slug}))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())

    def test_author_can_delete_own_post(self):
        self.client.force_login(self.author)
        response = self.client.post(reverse("post_delete", kwargs={"slug": self.post.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())

    def test_dashboard_lists_only_own_posts(self):
        make_post(self.other, "Rival Post")
        self.client.force_login(self.author)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Owned Post")
        self.assertNotContains(response, "Rival Post")


class CommentModerationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("writer", password="Str0ng!Passw0rd")
        self.reader = User.objects.create_user("reader", password="Str0ng!Passw0rd")
        self.post = make_post(self.author, "Discussable Post")

    def comment(self, body="Great write-up, thanks!"):
        return self.client.post(self.post.get_absolute_url(), {"body": body})

    def test_login_required_to_comment(self):
        response = self.comment()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertFalse(Comment.objects.exists())

    def test_comment_starts_unapproved_and_hidden(self):
        self.client.force_login(self.reader)
        self.comment("Nice one! Very helpful.")
        comment = Comment.objects.get()
        self.assertFalse(comment.approved)
        self.assertNotContains(self.client.get(self.post.get_absolute_url()), "Very helpful")

    def test_author_can_approve_and_it_appears(self):
        self.client.force_login(self.reader)
        self.comment("Nice one! Very helpful.")
        comment = Comment.objects.get()
        self.client.force_login(self.author)
        self.client.post(reverse("comment_moderate", kwargs={"pk": comment.pk, "action": "approve"}))
        comment.refresh_from_db()
        self.assertTrue(comment.approved)
        self.assertContains(self.client.get(self.post.get_absolute_url()), "Very helpful")

    def test_author_sees_pending_badge_on_own_post(self):
        self.client.force_login(self.reader)
        self.comment("Pending item here.")
        self.client.force_login(self.author)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, "Pending item here")
        self.assertContains(response, "pending")

    def test_only_post_author_can_moderate(self):
        self.client.force_login(self.reader)
        self.comment("I will try to approve myself.")
        comment = Comment.objects.get()
        response = self.client.post(reverse("comment_moderate", kwargs={"pk": comment.pk, "action": "approve"}))
        self.assertEqual(response.status_code, 404)
        comment.refresh_from_db()
        self.assertFalse(comment.approved)

    def test_short_comment_rejected(self):
        self.client.force_login(self.reader)
        self.comment("ok")
        self.assertFalse(Comment.objects.exists())


class SeederTests(TestCase):
    def test_seed_demo_populates_blog(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Post.objects.filter(status=Post.Status.PUBLISHED).count(), 6)
        self.assertGreaterEqual(Category.objects.count(), 4)
        self.assertTrue(Comment.objects.filter(approved=True).exists())
        self.assertTrue(Comment.objects.filter(approved=False).exists())  # a pending one for moderation demo
