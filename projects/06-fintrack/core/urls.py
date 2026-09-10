"""FinTrack — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    # ---- dashboard & reports ------------------------------------------------
    path("", views.index, name="home"),
    path("reports/", views.reports, name="reports"),

    # ---- accounts ------------------------------------------------------------
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/new/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),

    # ---- transactions ---------------------------------------------------------
    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/new/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("transactions/transfer/", views.transfer_create, name="transfer_create"),
    path("transactions/import/", views.csv_import, name="csv_import"),

    # ---- categories & budgets ---------------------------------------------------
    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("budgets/", views.budget_list, name="budget_list"),
    path("budgets/new/", views.budget_create, name="budget_create"),

    # ---- account -----------------------------------------------------------------
    path("profile/", views.profile, name="profile"),

    # ---- accounts (auth) ----------------------------------------------------------
    path("login/", auth_views.LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="registration/password_change_form.html", success_url="done"), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="registration/password_change_done.html"), name="password_change_done"),
]
