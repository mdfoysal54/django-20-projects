"""LearnHub domain tests: catalogue visibility, enrolment gating, progress, authoring."""
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Course, Enrollment, Lesson, LessonProgress


def make_course(instructor, title="Django Fundamentals", status=Course.Status.PUBLISHED, **kw):
    return Course.objects.create(instructor=instructor, title=title, status=status, **kw)


def make_lesson(course, order, title=None, duration=10):
    return Lesson.objects.create(
        course=course, order=order,
        title=title or f"Lesson {order}", duration_minutes=duration,
        content=f"Body of lesson {order}.",
    )


class CatalogueTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.published = make_course(self.instructor, "Published Course")
        self.draft = make_course(self.instructor, "Draft Course", status=Course.Status.DRAFT)
        make_lesson(self.published, 1)

    def test_catalog_shows_published_only(self):
        response = self.client.get(reverse("catalog"))
        self.assertContains(response, "Published Course")
        self.assertNotContains(response, "Draft Course")

    def test_instructor_sees_own_draft_but_others_do_not(self):
        self.client.force_login(self.instructor)
        self.assertContains(self.client.get(reverse("catalog")), "Draft Course")
        other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        self.client.force_login(other)
        self.assertNotContains(self.client.get(reverse("catalog")), "Draft Course")
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)

    def test_search_and_level_filters(self):
        make_course(self.instructor, "Advanced Kubernetes", level=Course.Level.ADVANCED)
        response = self.client.get(reverse("catalog"), {"q": "kubernetes"})
        self.assertContains(response, "Advanced Kubernetes")
        self.assertNotContains(response, "Published Course")
        response = self.client.get(reverse("catalog"), {"level": "advanced"})
        self.assertContains(response, "Advanced Kubernetes")
        self.assertNotContains(response, "Published Course")

    def test_course_page_lists_curriculum(self):
        make_lesson(self.published, 2, title="Models & Migrations")
        response = self.client.get(self.published.get_absolute_url())
        self.assertContains(response, "Models &amp; Migrations")


class EnrolmentTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.course = make_course(self.instructor, "Joinable Course")
        self.lessons = [make_lesson(self.course, i) for i in (1, 2, 3)]
        self.student = User.objects.create_user("learner", password="Str0ng!Passw0rd")

    def test_enroll_requires_login(self):
        response = self.client.post(reverse("enroll", kwargs={"slug": self.course.slug}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_enroll_creates_single_enrolment(self):
        self.client.force_login(self.student)
        self.client.post(reverse("enroll", kwargs={"slug": self.course.slug}))
        self.client.post(reverse("enroll", kwargs={"slug": self.course.slug}))
        self.assertEqual(Enrollment.objects.filter(student=self.student).count(), 1)

    def test_unenrolled_student_cannot_open_lessons(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("lesson_detail", kwargs={
            "slug": self.course.slug, "lesson_pk": self.lessons[0].pk,
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.course.get_absolute_url())
        self.assertFalse(LessonProgress.objects.exists())

    def test_instructor_can_preview_lessons(self):
        self.client.force_login(self.instructor)
        response = self.client.get(reverse("lesson_detail", kwargs={
            "slug": self.course.slug, "lesson_pk": self.lessons[0].pk,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lessons[0].title)


class ProgressTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.course = make_course(self.instructor, "Progress Course")
        self.lessons = [make_lesson(self.course, i) for i in (1, 2, 3, 4)]
        self.student = User.objects.create_user("learner", password="Str0ng!Passw0rd")
        self.client.force_login(self.student)
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)

    def complete(self, lesson):
        return self.client.post(reverse("lesson_complete", kwargs={
            "slug": self.course.slug, "lesson_pk": lesson.pk,
        }))

    def test_progress_percentage_and_completion(self):
        self.assertEqual(self.enrollment.progress_percent, 0)
        self.complete(self.lessons[0])
        self.assertEqual(self.enrollment.progress_percent, 25)
        self.complete(self.lessons[1])
        self.complete(self.lessons[2])
        self.assertEqual(self.enrollment.progress_percent, 75)
        response = self.complete(self.lessons[3])
        self.assertEqual(self.enrollment.progress_percent, 100)
        self.assertTrue(self.enrollment.is_finished)
        self.assertRedirects(response, self.course.get_absolute_url())

    def test_completing_lesson_redirects_to_next(self):
        response = self.complete(self.lessons[1])
        self.assertEqual(
            response.url,
            reverse("lesson_detail", kwargs={"slug": self.course.slug, "lesson_pk": self.lessons[2].pk}),
        )

    def test_lesson_completion_is_idempotent(self):
        self.complete(self.lessons[0])
        self.complete(self.lessons[0])
        self.assertEqual(LessonProgress.objects.filter(completed=True).count(), 1)

    def test_progress_of_another_student_cannot_be_written(self):
        other = User.objects.create_user("sneaky", password="Str0ng!Passw0rd")
        self.client.force_login(other)   # not enrolled in this course
        response = self.complete(self.lessons[0])
        self.assertEqual(response.status_code, 302)
        self.assertFalse(LessonProgress.objects.filter(enrollment=self.enrollment).exists())


class AuthoringTests(TestCase):
    def setUp(self):
        self.instructor = User.objects.create_user("teacher", password="Str0ng!Passw0rd")
        self.other = User.objects.create_user("someone", password="Str0ng!Passw0rd")
        self.course = make_course(self.instructor, "My Course", status=Course.Status.DRAFT)

    def test_instructor_creates_course_as_draft(self):
        self.client.force_login(self.instructor)
        response = self.client.post(reverse("course_create"), {
            "title": "Async Django Deep Dive",
            "summary": "Celery, channels and background work.",
            "description": "A deep dive into asynchronous Django.",
            "level": Course.Level.INTERMEDIATE,
            "price": "49.00",
        })
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(title="Async Django Deep Dive")
        self.assertEqual(course.instructor, self.instructor)
        self.assertEqual(course.status, Course.Status.DRAFT)

    def test_non_instructor_cannot_edit_course(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("course_edit", kwargs={"slug": self.course.slug}))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(reverse("lesson_create", kwargs={"slug": self.course.slug}), {
            "title": "Hack lesson", "order": 1, "duration_minutes": 5, "content": "x",
        })
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Lesson.objects.exists())

    def test_publish_requires_lessons(self):
        self.client.force_login(self.instructor)
        self.client.post(reverse("course_edit", kwargs={"slug": self.course.slug}), {"action": "publish"})
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.Status.DRAFT)   # blocked

        make_lesson(self.course, 1)
        self.client.post(reverse("course_edit", kwargs={"slug": self.course.slug}), {"action": "publish"})
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, Course.Status.PUBLISHED)

    def test_lesson_order_collision_rejected(self):
        self.client.force_login(self.instructor)
        make_lesson(self.course, 1)
        response = self.client.post(reverse("lesson_create", kwargs={"slug": self.course.slug}), {
            "title": "Clash", "order": 1, "duration_minutes": 5, "content": "x",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already uses this position")
        self.assertEqual(Lesson.objects.count(), 1)

    def test_lesson_form_suggests_next_order(self):
        self.client.force_login(self.instructor)
        make_lesson(self.course, 1)
        make_lesson(self.course, 2)
        response = self.client.get(reverse("lesson_create", kwargs={"slug": self.course.slug}))
        self.assertContains(response, 'value="3"')


class SeederTests(TestCase):
    def test_seed_demo_populates_lms(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Course.objects.filter(status=Course.Status.PUBLISHED).count(), 5)
        self.assertGreaterEqual(Lesson.objects.count(), 20)
        self.assertTrue(Enrollment.objects.exists())
        self.assertTrue(LessonProgress.objects.filter(completed=True).exists())
