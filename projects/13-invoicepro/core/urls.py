"""InvoicePro — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # ---- clients ------------------------------------------------------------
    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_form, name="client_create"),
    path("clients/<int:pk>/edit/", views.client_form, name="client_edit"),

    # ---- invoices -----------------------------------------------------------
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/new/", views.invoice_form, name="invoice_create"),
    path("invoices/<str:number>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<str:number>/edit/", views.invoice_form, name="invoice_edit"),
    path("invoices/<str:number>/send/", views.invoice_send, name="invoice_send"),
    path("invoices/<str:number>/void/", views.invoice_void, name="invoice_void"),
    path("invoices/<str:number>/delete/", views.invoice_delete, name="invoice_delete"),
    path("invoices/<str:number>/pay/", views.invoice_pay, name="invoice_pay"),
    path("payments/<int:pk>/delete/", views.payment_delete, name="payment_delete"),

    # ---- reports ------------------------------------------------------------
    path("aging/", views.aging, name="aging"),
    path("expenses/", views.expenses, name="expenses"),

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
