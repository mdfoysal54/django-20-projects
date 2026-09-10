"""LearnHub — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- catalogue --------------------------------------------------------
    path("", views.index, name="home"),
    path("courses/", views.catalog, name="catalog"),
    path("courses/<slug:slug>/", views.course_detail, name="course_detail"),

    # ---- learning ---------------------------------------------------------
    path("courses/<slug:slug>/enroll/", views.enroll, name="enroll"),
    path("my-learning/", views.my_learning, name="my_learning"),
    path("courses/<slug:slug>/lessons/<int:lesson_pk>/", views.lesson_detail, name="lesson_detail"),
    path("courses/<slug:slug>/lessons/<int:lesson_pk>/complete/", views.lesson_complete, name="lesson_complete"),

    # ---- instructor -------------------------------------------------------
    path("teach/", views.teach, name="teach"),
    path("teach/new/", views.course_create, name="course_create"),
    path("teach/<slug:slug>/edit/", views.course_edit, name="course_edit"),
    path("teach/<slug:slug>/lessons/new/", views.lesson_create, name="lesson_create"),

    # ---- account ----------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) ---------------------------------------------------
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html", success_url="done",
        ),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password_change_done",
    ),
]
