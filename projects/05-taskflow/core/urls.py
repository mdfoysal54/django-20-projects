"""TaskFlow — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- dashboard & feed --------------------------------------------------
    path("", views.index, name="home"),
    path("activity/", views.activity_feed, name="activity"),
    path("my-tasks/", views.my_tasks, name="my_tasks"),

    # ---- projects -----------------------------------------------------------
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<slug:slug>/", views.project_detail, name="project_detail"),
    path("projects/<slug:slug>/edit/", views.project_edit, name="project_edit"),
    path("projects/<slug:slug>/archive/", views.project_archive, name="project_archive"),
    path("projects/<slug:slug>/members/", views.member_list, name="member_list"),
    path("projects/<slug:slug>/members/<int:user_id>/remove/", views.member_remove, name="member_remove"),

    # ---- tasks --------------------------------------------------------------
    path("projects/<slug:slug>/tasks/new/", views.task_create, name="task_create"),
    path("projects/<slug:slug>/tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("projects/<slug:slug>/tasks/<int:pk>/move/", views.task_move, name="task_move"),
    path("projects/<slug:slug>/tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),

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
