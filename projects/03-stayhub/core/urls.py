"""StayHub — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- public -----------------------------------------------------------
    path("", views.index, name="home"),
    path("search/", views.search, name="search"),
    path("hotels/<slug:slug>/", views.hotel_detail, name="hotel_detail"),

    # ---- booking ----------------------------------------------------------
    path("rooms/<int:room_pk>/book/", views.booking_create, name="booking_create"),
    path("bookings/", views.my_bookings, name="my_bookings"),
    path("bookings/<int:pk>/", views.booking_detail, name="booking_detail"),
    path("bookings/<int:pk>/cancel/", views.booking_cancel, name="booking_cancel"),

    # ---- host area ---------------------------------------------------------
    path("manage/", views.manage_hotels, name="manage_hotels"),
    path("manage/<slug:slug>/rooms/", views.manage_rooms, name="manage_rooms"),

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
