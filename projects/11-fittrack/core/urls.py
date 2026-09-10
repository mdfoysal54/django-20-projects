"""FitTrack — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # ---- workouts -----------------------------------------------------------
    path("workouts/", views.workout_list, name="workout_list"),
    path("workouts/new/", views.workout_create, name="workout_create"),
    path("workouts/<int:pk>/", views.workout_detail, name="workout_detail"),
    path("workouts/<int:pk>/edit/", views.workout_edit, name="workout_edit"),
    path("workouts/<int:pk>/sets/add/", views.add_set, name="add_set"),
    path("workouts/<int:pk>/delete/", views.delete_workout, name="delete_workout"),
    path("sets/<int:pk>/delete/", views.delete_set, name="delete_set"),

    # ---- exercises ----------------------------------------------------------
    path("exercises/", views.exercise_list, name="exercise_list"),
    path("exercises/new/", views.exercise_create, name="exercise_create"),
    path("exercises/<slug:slug>/", views.exercise_detail, name="exercise_detail"),

    # ---- goals & measurements ----------------------------------------------
    path("goals/", views.goals, name="goals"),
    path("goals/<int:pk>/close/", views.goal_close, name="goal_close"),
    path("bodyweight/", views.bodyweight, name="bodyweight"),
    path("bodyweight/log/", views.log_weight, name="log_weight"),

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
