"""LinkShort — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),

    # ---- the redirect endpoint (public, hot path) ---------------------------
    path("s/<str:code>/", views.redirect_link, name="redirect_link"),
    path("s/<str:code>/preview/", views.link_preview, name="link_preview"),

    # ---- dashboard ----------------------------------------------------------
    path("dashboard/", views.dashboard, name="dashboard"),
    path("links/new/", views.link_create, name="link_create"),
    path("links/quick/", views.quick_shorten, name="quick_shorten"),
    path("links/<str:code>/", views.link_detail, name="link_detail"),
    path("links/<str:code>/edit/", views.link_edit, name="link_edit"),
    path("links/<str:code>/toggle/", views.link_toggle, name="link_toggle"),
    path("links/<str:code>/delete/", views.link_delete, name="link_delete"),
    path("analytics/", views.analytics, name="analytics"),

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
