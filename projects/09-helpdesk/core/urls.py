"""HelpDesk — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),

    # ---- customer -----------------------------------------------------------
    path("tickets/", views.my_tickets, name="my_tickets"),
    path("tickets/new/", views.new_ticket, name="new_ticket"),
    path("tickets/<str:reference>/", views.ticket_detail, name="ticket_detail"),
    path("tickets/<str:reference>/feedback/", views.give_feedback, name="give_feedback"),

    # ---- agents -------------------------------------------------------------
    path("queue/", views.queue, name="queue"),
    path("queue/<str:reference>/claim/", views.claim, name="claim"),
    path("queue/<str:reference>/status/<str:status>/", views.quick_status, name="quick_status"),
    path("metrics/", views.metrics, name="metrics"),
    path("departments/", views.departments, name="departments"),

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
