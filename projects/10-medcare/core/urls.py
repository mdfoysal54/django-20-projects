"""MedCare — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/<int:pk>/", views.doctor_detail, name="doctor_detail"),
    path("doctors/<int:pk>/book/", views.book, name="book"),

    # ---- patient ------------------------------------------------------------
    path("appointments/", views.my_appointments, name="my_appointments"),
    path("appointments/<str:reference>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<str:reference>/cancel/", views.cancel, name="cancel"),
    path("appointments/<str:reference>/note/", views.update_note, name="update_note"),

    # ---- clinic -------------------------------------------------------------
    path("clinic/schedule/", views.schedule, name="schedule"),
    path("clinic/availability/", views.availability, name="availability"),
    path("clinic/profile/", views.update_doctor_profile, name="update_doctor_profile"),

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
