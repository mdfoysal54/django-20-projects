"""EventTix — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("events/", views.event_list, name="event_list"),
    path("events/<slug:slug>/", views.event_detail, name="event_detail"),
    path("events/<slug:slug>/book/", views.book, name="book"),

    # ---- my tickets ---------------------------------------------------------
    path("tickets/", views.my_bookings, name="my_bookings"),
    path("tickets/<str:reference>/", views.booking_detail, name="booking_detail"),
    path("tickets/<str:reference>/cancel/", views.booking_cancel, name="booking_cancel"),
    path("tickets/<str:reference>/stub/", views.ticket_stub, name="ticket_stub"),

    # ---- organiser ----------------------------------------------------------
    path("organise/", views.organiser_dashboard, name="organiser_dashboard"),
    path("organise/new/", views.event_create, name="event_create"),
    path("organise/<slug:slug>/", views.event_manage, name="event_manage"),
    path("organise/<slug:slug>/status/", views.event_set_status, name="event_set_status"),
    path("organise/<slug:slug>/attendees/", views.event_attendees, name="event_attendees"),
    path("organise/<slug:slug>/door/", views.door_scan, name="door_scan"),
    path("organise/<slug:slug>/door/lookup/", views.door_lookup, name="door_lookup"),
    path("organise/<slug:slug>/door/<str:reference>/", views.door_check_in, name="door_check_in"),

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
