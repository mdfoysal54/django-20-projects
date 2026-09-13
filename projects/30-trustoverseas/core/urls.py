"""Trust Overseas Ltd — application URL configuration."""
from django.contrib.auth import views as auth_views
from django.urls import path

from .auth_views import RegisterView
from . import views

urlpatterns = [
    path("", views.index, name="home"),
    path("destinations/", views.destinations, name="destinations"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("track/", views.track, name="track"),

    path("desk/", views.dashboard, name="dashboard"),
    path("portal/", views.client_portal, name="portal"),
    path("agent/", views.agent_desk, name="agent_desk"),
    path("profile/", views.profile, name="profile"),

    # CRM
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/new/", views.lead_new, name="lead_new"),
    path("leads/<int:pk>/win/", views.lead_win, name="lead_win"),
    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_form, name="client_create"),
    path("clients/<str:code>/", views.client_detail, name="client_detail"),
    path("clients/<str:code>/edit/", views.client_form, name="client_edit"),
    path("agents/", views.agent_list, name="agent_list"),
    path("agents/new/", views.agent_form, name="agent_create"),
    path("agents/<int:pk>/edit/", views.agent_form, name="agent_edit"),

    # Vault
    path("vault/", views.vault, name="vault"),
    path("passports/new/", views.passport_form, name="passport_create"),
    path("passports/<str:number>/", views.passport_detail, name="passport_detail"),
    path("passports/<str:number>/move/", views.passport_move, name="passport_move"),

    # Cases
    path("cases/", views.case_list, name="case_list"),
    path("cases/new/", views.case_open, name="case_open"),
    path("cases/<str:number>/", views.case_detail, name="case_detail"),
    path("cases/<str:number>/advance/", views.case_advance, name="case_advance"),
    path("cases/<str:number>/document/", views.case_document, name="case_document"),
    path("cases/<str:number>/medical/", views.case_medical, name="case_medical"),
    path("cases/<str:number>/attest/", views.case_attest, name="case_attest"),
    path("cases/<str:number>/portal/", views.case_portal, name="case_portal"),
    path("cases/<str:number>/invoice/", views.case_invoice, name="case_invoice"),
    path("cases/<str:number>/visa.pdf", views.visa_download, name="visa_download"),

    # GAMCA / attestation / GCC boards
    path("gamca/", views.gamca_board, name="gamca_board"),
    path("attestation/", views.attest_board, name="attest_board"),
    path("portals/", views.portal_board, name="portal_board"),

    # Accounts
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<str:number>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<str:number>/pay/", views.invoice_pay, name="invoice_pay"),
    path("ledger/", views.ledger, name="ledger"),
    path("trial/", views.trial, name="trial"),
    path("petty/", views.petty, name="petty"),
    path("coa/", views.coa, name="coa"),
    path("audit/", views.audit, name="audit"),

    # HR
    path("hr/", views.hr_desk, name="hr_desk"),
    path("hr/clock/", views.hr_clock, name="hr_clock"),
    path("hr/leave/", views.hr_leave, name="hr_leave"),
    path("hr/leave/<int:pk>/<str:decision>/", views.hr_leave_decide, name="hr_leave_decide"),
    path("hr/payroll/", views.hr_payroll, name="hr_payroll"),
    path("hr/staff/<str:code>/pay/", views.hr_run_pay, name="hr_run_pay"),

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/register/", RegisterView.as_view(), name="register"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url="done",
        ),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
