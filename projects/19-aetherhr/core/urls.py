"""AetherHR URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("people/", views.people, name="people"),
    path("people/<str:code>/", views.employee_detail, name="employee_detail"),
    path("org/", views.org, name="org"),
    path("clock/", views.clock, name="clock"),
    path("leave/", views.leave_list, name="leave_list"),
    path("leave/new/", views.leave_new, name="leave_new"),
    path("leave/<int:pk>/", views.leave_detail, name="leave_detail"),
    path("leave/<int:pk>/decide/", views.leave_decide, name="leave_decide"),
    path("payroll/", views.payroll, name="payroll"),
    path("payroll/<int:pk>/", views.payslip_detail, name="payslip_detail"),
    path("jobs/", views.jobs, name="jobs"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/advance/<int:app>/", views.applicant_advance, name="applicant_advance"),
    path("reviews/", views.reviews, name="reviews"),
    path("assets/", views.assets, name="assets"),
    path("news/", views.news, name="news"),
    path("reports/headcount/", views.report_headcount, name="report_headcount"),
    path("reports/leave/", views.report_leave, name="report_leave"),
    path("settings/", views.settings_hub, name="settings_hub"),
    path("profile/", views.profile, name="profile"),
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
