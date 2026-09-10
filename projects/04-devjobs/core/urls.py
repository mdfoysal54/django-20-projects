"""DevJobs — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- public -----------------------------------------------------------
    path("", views.index, name="home"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<slug:slug>/", views.job_detail, name="job_detail"),
    path("companies/<slug:slug>/", views.company_detail, name="company_detail"),

    # ---- candidate ---------------------------------------------------------
    path("jobs/<slug:slug>/apply/", views.apply_job, name="apply_job"),
    path("jobs/<slug:slug>/save/", views.toggle_save, name="toggle_save"),
    path("my-applications/", views.my_applications, name="my_applications"),
    path("applications/<int:pk>/withdraw/", views.withdraw_application, name="withdraw_application"),
    path("saved-jobs/", views.saved_jobs, name="saved_jobs"),

    # ---- employer -----------------------------------------------------------
    path("employer/", views.dashboard, name="dashboard"),
    path("employer/company/new/", views.company_create, name="company_create"),
    path("employer/jobs/new/", views.job_create, name="job_create"),
    path("employer/jobs/<slug:slug>/edit/", views.job_edit, name="job_edit"),
    path("employer/jobs/<slug:slug>/applicants/", views.job_applicants, name="job_applicants"),
    path("employer/applications/<int:pk>/review/", views.application_review, name="application_review"),

    # ---- account -------------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) ------------------------------------------------------
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
