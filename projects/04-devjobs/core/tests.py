"""DevJobs domain tests — job lifecycle, application rules, employer scoping."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Application, Company, Job, SavedJob


def make_company(owner, name="Acme QA"):
    return Company.objects.create(owner=owner, name=name, location="Dhaka")


def make_job(company, recruiter, title="Django Engineer", status=Job.Status.OPEN, **kw):
    return Job.objects.create(
        company=company, posted_by=recruiter, title=title, status=status,
        description="Build things with Django and PostgreSQL all day long. " * 2, **kw
    )


class JobLifecycleTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user("recruiter", password="Str0ng!Passw0rd")
        self.company = make_company(self.recruiter)

    def test_salary_display_variants(self):
        job = make_job(self.company, self.recruiter, salary_min=5000, salary_max=9000)
        self.assertEqual(job.salary_display, "USD 5,000 – 9,000")
        job.salary_max = None
        job.save()
        self.assertEqual(job.salary_display, "USD 5,000+")
        job.salary_min = None
        job.save()
        self.assertEqual(job.salary_display, "Salary not disclosed")

    def test_min_greater_than_max_is_invalid(self):
        job = make_job(self.company, self.recruiter, salary_min=9000, salary_max=5000)
        with self.assertRaises(ValidationError):
            job.full_clean()

    def test_expired_job_is_not_open(self):
        job = make_job(self.company, self.recruiter, deadline=timezone.localdate() - timedelta(days=1))
        self.assertTrue(job.is_expired)
        self.assertFalse(job.is_open)

    def test_applications_blocked_after_deadline(self):
        job = make_job(self.company, self.recruiter, deadline=timezone.localdate() - timedelta(days=1))
        candidate = User.objects.create_user("candidate", password="Str0ng!Passw0rd")
        self.client.force_login(candidate)
        response = self.client.get(reverse("apply_job", kwargs={"slug": job.slug}))
        self.assertEqual(response.status_code, 302)   # bounced
        self.assertFalse(Application.objects.exists())

    def test_draft_jobs_are_invisible_to_candidates(self):
        make_job(self.company, self.recruiter, title="Secret Role", status=Job.Status.DRAFT)
        self.assertNotContains(self.client.get(reverse("job_list")), "Secret Role")
        self.client.force_login(self.recruiter)
        self.assertContains(self.client.get(reverse("job_list")), "Secret Role")


class SearchTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user("recruiter", password="Str0ng!Passw0rd")
        self.company = make_company(self.recruiter, "Nimbus Cloud")
        self.job = make_job(self.company, self.recruiter, title="Senior Python Developer",
                            tags="Python, Django, AWS", location="Remote (EU)", level=Job.Level.SENIOR)

    def test_keyword_search_hits_title_tags_and_company(self):
        for term in ("python", "aws", "nimbus"):
            response = self.client.get(reverse("job_list"), {"q": term})
            self.assertContains(response, "Senior Python Developer", msg_prefix=term)

    def test_level_and_location_filters(self):
        response = self.client.get(reverse("job_list"), {"level": "junior"})
        self.assertNotContains(response, "Senior Python Developer")
        response = self.client.get(reverse("job_list"), {"location": "berlin"})
        self.assertNotContains(response, "Senior Python Developer")


class ApplicationTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user("recruiter", password="Str0ng!Passw0rd")
        self.company = make_company(self.recruiter)
        self.job = make_job(self.company, self.recruiter)
        self.candidate = User.objects.create_user("candidate", password="Str0ng!Passw0rd")

    def apply(self, **overrides):
        data = {
            "cover_letter": "I have shipped Django apps for six years and love this product space.",
            "portfolio_url": "",
        }
        data.update(overrides)
        return self.client.post(reverse("apply_job", kwargs={"slug": self.job.slug}), data)

    def test_apply_requires_login(self):
        response = self.apply()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_apply_once_only(self):
        self.client.force_login(self.candidate)
        self.assertEqual(self.apply().status_code, 302)
        self.apply()   # second attempt
        self.assertEqual(Application.objects.count(), 1)

    def test_short_cover_letter_rejected(self):
        self.client.force_login(self.candidate)
        response = self.apply(cover_letter="hire me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Application.objects.count(), 0)

    def test_recruiter_cannot_apply_to_own_job(self):
        self.client.force_login(self.recruiter)
        response = self.apply()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Application.objects.exists())

    def test_resume_upload_happy_path(self):
        self.client.force_login(self.candidate)
        resume = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 fake resume", content_type="application/pdf")
        response = self.client.post(reverse("apply_job", kwargs={"slug": self.job.slug}), {
            "cover_letter": "Ten years of Django, shipped products end to end.",
            "resume": resume,
            "portfolio_url": "https://example.com/me",
        })
        self.assertEqual(response.status_code, 302)
        application = Application.objects.get()
        self.assertTrue(application.resume.name.endswith(".pdf"))

    def test_resume_extension_blocklist(self):
        self.client.force_login(self.candidate)
        evil = SimpleUploadedFile("payload.exe", b"MZ\x90\x00", content_type="application/x-msdownload")
        response = self.client.post(reverse("apply_job", kwargs={"slug": self.job.slug}), {
            "cover_letter": "Ten years of Django, shipped products end to end.",
            "resume": evil,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported file type")
        self.assertFalse(Application.objects.exists())

    def test_resume_size_cap(self):
        self.client.logout()
        self.client.force_login(self.candidate)
        big = SimpleUploadedFile("cv.pdf", b"x" * (2 * 1024 * 1024 + 1), content_type="application/pdf")
        response = self.client.post(reverse("apply_job", kwargs={"slug": self.job.slug}), {
            "cover_letter": "Ten years of Django, shipped products end to end.",
            "resume": big,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 MB")
        self.assertFalse(Application.objects.exists())

    def test_withdraw_and_no_reapply(self):
        self.client.force_login(self.candidate)
        self.apply()
        application = Application.objects.get()
        response = self.client.post(reverse("withdraw_application", kwargs={"pk": application.pk}))
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.WITHDRAWN)
        self.assertFalse(application.is_active)

    def test_cannot_withdraw_someone_elses_application(self):
        self.client.force_login(self.candidate)
        self.apply()
        application = Application.objects.get()
        intruder = User.objects.create_user("intruder", password="Str0ng!Passw0rd")
        self.client.force_login(intruder)
        response = self.client.post(reverse("withdraw_application", kwargs={"pk": application.pk}))
        self.assertEqual(response.status_code, 404)
        application.refresh_from_db()
        self.assertEqual(application.status, Application.Status.SUBMITTED)


class EmployerToolTests(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user("recruiter", password="Str0ng!Passw0rd")
        self.company = make_company(self.recruiter)
        self.job = make_job(self.company, self.recruiter)
        self.other = User.objects.create_user("other", password="Str0ng!Passw0rd")
        self.candidate = User.objects.create_user("candidate", password="Str0ng!Passw0rd")
        self.application = Application.objects.create(
            job=self.job, applicant=self.candidate, cover_letter="Please hire me, I am great."
        )

    def test_dashboard_lists_only_own_jobs(self):
        other_company = make_company(self.other, "Other Corp")
        make_job(other_company, self.other, title="Unrelated Role")
        self.client.force_login(self.recruiter)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, self.job.title)
        self.assertNotContains(response, "Unrelated Role")

    def test_stranger_cannot_open_applicants_page(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("job_applicants", kwargs={"slug": self.job.slug}))
        self.assertEqual(response.status_code, 404)

    def test_stranger_cannot_edit_application_status(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("application_review", kwargs={"pk": self.application.pk}),
            {"status": Application.Status.HIRED, "employer_notes": "hacked"},
        )
        self.assertEqual(response.status_code, 404)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.SUBMITTED)

    def test_recruiter_moves_candidate_through_pipeline(self):
        self.client.force_login(self.recruiter)
        response = self.client.post(
            reverse("application_review", kwargs={"pk": self.application.pk}),
            {"status": Application.Status.INTERVIEW, "employer_notes": "Strong portfolio."},
        )
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.INTERVIEW)
        self.assertEqual(self.application.status_badge, "badge-warn")

    def test_job_can_be_closed_and_reopened(self):
        self.client.force_login(self.recruiter)
        self.client.post(reverse("job_edit", kwargs={"slug": self.job.slug}), {"action": "toggle_open"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.CLOSED)
        self.client.post(reverse("job_edit", kwargs={"slug": self.job.slug}), {"action": "toggle_open"})
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, Job.Status.OPEN)

    def test_saved_jobs_toggle(self):
        self.client.force_login(self.candidate)
        url = reverse("toggle_save", kwargs={"slug": self.job.slug})
        self.client.post(url)
        self.assertEqual(SavedJob.objects.count(), 1)
        self.client.post(url)
        self.assertEqual(SavedJob.objects.count(), 0)


class SeederTests(TestCase):
    def test_seed_demo_populates_board(self):
        call_command("seed_demo", force=True)
        self.assertGreaterEqual(Company.objects.count(), 4)
        self.assertGreaterEqual(Job.objects.filter(status=Job.Status.OPEN).count(), 8)
        self.assertTrue(Application.objects.exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
