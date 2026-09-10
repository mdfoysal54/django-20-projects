"""AttendX — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),

    # ---- cohorts ------------------------------------------------------------
    path("cohorts/", views.cohort_list, name="cohort_list"),
    path("cohorts/new/", views.cohort_create, name="cohort_create"),
    path("cohorts/join/", views.cohort_join, name="cohort_join"),
    path("cohorts/<int:pk>/", views.cohort_detail, name="cohort_detail"),
    path("cohorts/<int:pk>/edit/", views.cohort_edit, name="cohort_edit"),
    path("cohorts/<int:pk>/remove/", views.cohort_remove_student, name="cohort_remove_student"),
    path("cohorts/<int:pk>/sessions/new/", views.session_create, name="session_create"),
    path("cohorts/<int:pk>/report/", views.report, name="report"),

    # ---- sessions & register ------------------------------------------------
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/status/<str:status>/", views.session_set_status, name="session_set_status"),
    path("sessions/<int:pk>/register/", views.take_attendance, name="take_attendance"),

    # ---- student ------------------------------------------------------------
    path("my-attendance/", views.my_attendance, name="my_attendance"),

    # ---- account ------------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) ----------------------------------------------------
    path("accounts/login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path("accounts/password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("accounts/password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
