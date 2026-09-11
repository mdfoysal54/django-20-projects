"""OrbitPay URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("ledger/", views.transfer_list, name="transfer_list"),
    path("send/", views.transfer_new, name="transfer_new"),
    path("pay/<str:number>/", views.transfer_detail, name="transfer_detail"),
    path("@<slug:handle>/", views.account_detail, name="account_detail"),


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

