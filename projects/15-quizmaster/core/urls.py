"""QuizMaster — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("quizzes/", views.quiz_list, name="quiz_list"),
    path("quizzes/<slug:slug>/", views.quiz_detail, name="quiz_detail"),
    path("quizzes/<slug:slug>/start/", views.start_attempt, name="start_attempt"),
    path("quizzes/<slug:slug>/results/", views.quiz_results, name="quiz_results"),

    # ---- taking quizzes -----------------------------------------------------
    path("attempts/<int:pk>/", views.take_quiz, name="take_quiz"),
    path("attempts/<int:pk>/result/", views.attempt_result, name="attempt_result"),
    path("my-attempts/", views.my_attempts, name="my_attempts"),

    # ---- authoring ----------------------------------------------------------
    path("studio/", views.my_quizzes, name="my_quizzes"),
    path("studio/new/", views.quiz_create, name="quiz_create"),
    path("studio/<slug:slug>/edit/", views.quiz_edit, name="quiz_edit"),
    path("studio/<slug:slug>/delete/", views.quiz_delete, name="quiz_delete"),
    path("studio/<slug:slug>/questions/new/", views.question_form, name="question_create"),
    path("studio/<slug:slug>/questions/<int:pk>/edit/", views.question_form, name="question_edit"),
    path("studio/<slug:slug>/questions/<int:pk>/delete/", views.question_delete, name="question_delete"),
    path("categories/", views.categories, name="categories"),

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
