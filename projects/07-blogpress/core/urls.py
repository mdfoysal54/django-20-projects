"""BlogPress — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("posts/", views.post_list, name="post_list"),
    path("posts/<slug:slug>/", views.post_detail, name="post_detail"),

    # ---- authoring ---------------------------------------------------------
    path("write/", views.dashboard, name="dashboard"),
    path("write/new/", views.post_create, name="post_create"),
    path("write/<slug:slug>/edit/", views.post_edit, name="post_edit"),
    path("write/<slug:slug>/publish/", views.post_toggle_publish, name="post_toggle_publish"),
    path("write/<slug:slug>/delete/", views.post_delete, name="post_delete"),
    path("comments/<int:pk>/<str:action>/", views.comment_moderate, name="comment_moderate"),

    # ---- account -----------------------------------------------------------
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
