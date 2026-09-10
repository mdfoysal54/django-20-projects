"""CampusOS URLs."""
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .auth_views import RegisterView

urlpatterns = [
    path("", views.index, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("students/", views.student_list, name="student_list"),
    path("students/new/", views.student_form, name="student_create"),
    path("students/<str:number>/", views.student_detail, name="student_detail"),
    path("students/<str:number>/enrol/", views.student_enrol, name="student_enrol"),
    path("admissions/", views.admissions, name="admissions"),
    path("guardians/", views.guardian_list, name="guardian_list"),
    path("fees/", views.fee_list, name="fee_list"),
    path("fees/new/", views.fee_create, name="fee_create"),
    path("fees/<str:number>/", views.invoice_detail, name="invoice_detail"),
    path("fees/<str:number>/pay/", views.invoice_pay, name="invoice_pay"),
    path("attendance/", views.attendance, name="attendance"),
    path("exams/", views.exam_list, name="exam_list"),
    path("exams/<int:pk>/", views.exam_detail, name="exam_detail"),
    path("timetable/", views.timetable, name="timetable"),
    path("staff/", views.staff_list, name="staff_list"),
    path("library/", views.library, name="library"),
    path("library/<int:pk>/loan/", views.loan_book, name="loan_book"),
    path("library/loan/<int:pk>/return/", views.loan_return, name="loan_return"),
    path("transport/", views.transport, name="transport"),
    path("notices/", views.notices, name="notices"),
    path("reports/fees/", views.report_fees, name="report_fees"),
    path("reports/results/", views.report_results, name="report_results"),
    path("reports/attendance/", views.report_attendance, name="report_attendance"),
    path("sms/", views.sms_list, name="sms_list"),
    path("settings/", views.settings_hub, name="settings_hub"),
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
