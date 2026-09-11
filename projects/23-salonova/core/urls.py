"""Salonova URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("bookings/", views.appointment_list, name="appointment_list"),
    path("bookings/new/", views.appointment_new, name="appointment_new"),
    path("bookings/<str:number>/", views.appointment_detail, name="appointment_detail"),
    path("services/", views.service_list, name="service_list"),


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

