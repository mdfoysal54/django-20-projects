"""Seed Trust Overseas Ltd with a working Dhaka recruiting house."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    ZERO, Attestation, Branch, CaseDocument, Client, Department, Lead, Passport,
    PortalSubmission, Staff, SubAgent, VisaCase,
)
from core.services import (
    advance_case, clock_in, ensure_coa, open_case, petty_out, raise_invoice,
    record_medical, request_leave, run_payroll, take_receipt,
)


class Command(BaseCommand):
    help = "Create a demo Trust Overseas house: files, GAMCA, vault, ledger, HR."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            self.stderr.write(self.style.ERROR("Refusing to seed with DEBUG=False. Pass --force."))
            return

        ensure_coa()
        today = timezone.localdate()
        branch = Branch.hq()
        dept, _ = Department.objects.get_or_create(branch=branch, name="Operations")

        admin, created = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@trustoverseas.dev",
                                        "first_name": "Faisal", "last_name": "Ahmed"},
        )
        if created:
            admin.set_password("admin")
        admin.is_staff = admin.is_superuser = True
        admin.save()
        Staff.objects.update_or_create(
            user=admin, defaults={"branch": branch, "department": dept, "code": "ST-000",
                                  "role": Staff.Role.SUPER, "designation": "Managing director",
                                  "base_salary": Decimal("0")},
        )

        alice, created = User.objects.get_or_create(
            username="alice", defaults={"email": "alice@trustoverseas.dev",
                                        "first_name": "Alice", "last_name": "Rahman"},
        )
        if created:
            alice.set_password("DemoPass123!")
            alice.save()
        officer, _ = Staff.objects.update_or_create(
            user=alice, defaults={"branch": branch, "department": dept, "code": "ST-001",
                                  "role": Staff.Role.CASE, "designation": "Case manager",
                                  "phone": "01711000001", "base_salary": Decimal("42000"),
                                  "hire_date": today - timedelta(days=400)},
        )

        karim_user, created = User.objects.get_or_create(
            username="karim", defaults={"email": "karim@example.com",
                                        "first_name": "Karim", "last_name": "Mia"},
        )
        if created:
            karim_user.set_password("DemoPass123!")
            karim_user.save()

        hasan_user, created = User.objects.get_or_create(
            username="hasan", defaults={"email": "hasan@agents.dev",
                                        "first_name": "Hasan", "last_name": "Ali"},
        )
        if created:
            hasan_user.set_password("DemoPass123!")
            hasan_user.save()

        agent_ok, _ = SubAgent.objects.update_or_create(
            name="Sylhet Bridge",
            defaults={"contact": "Rina Begum", "phone": "01718000001", "district": "Sylhet",
                      "credit_limit": Decimal("500000"), "commission_value": Decimal("4000")},
        )
        agent_lock, _ = SubAgent.objects.update_or_create(
            name="Rangpur Desk",
            defaults={"user": hasan_user, "contact": "Hasan Ali", "phone": "01718000002",
                      "email": "hasan@agents.dev", "district": "Rangpur",
                      "credit_limit": Decimal("10000"), "commission_value": Decimal("2500")},
        )

        def client(first, last, phone, pin, agent=None, **extra):
            obj, _ = Client.objects.update_or_create(
                phone=phone,
                defaults={"first_name": first, "last_name": last, "pin": pin,
                          "kyc": Client.KYC.OK, "district": extra.get("district", "Dhaka"),
                          "trade": extra.get("trade", "Mason"), "agent": agent,
                          "desk": officer, "source": extra.get("source", "walk-in"),
                          "user": extra.get("user")},
            )
            return obj

        c_karim = client("Karim", "Mia", "01710000001", "123456", user=karim_user, trade="Electrician")
        c_nabil = client("Nabil", "Hossain", "01710000002", "654321", agent=agent_ok, district="Sylhet",
                         trade="Welder")
        c_rafiq = client("Rafiq", "Uddin", "01710000003", "111222", agent=agent_lock, district="Rangpur",
                         trade="Driver")
        c_sadia = client("Sadia", "Akter", "01710000004", "333444", trade="Nurse", district="Chattogram")

        def passport(owner, number, days, loc=Passport.Loc.VAULT):
            obj, _ = Passport.objects.update_or_create(
                number=number,
                defaults={"client": owner, "issue_date": today - timedelta(days=200),
                          "expiry_date": today + timedelta(days=days), "blank_pages": 8,
                          "location": loc, "place_of_issue": "Dhaka", "envelope": f"ENV-{number[-4:]}"},
            )
            return obj

        p_karim = passport(c_karim, "A12345678", 900)
        p_nabil = passport(c_nabil, "B23456789", 640)
        p_rafiq = passport(c_rafiq, "C34567890", 500)
        p_sadia = passport(c_sadia, "D45678901", 120)  # under 190 — vault only
        passport(c_karim, "A00011122", 80, loc=Passport.Loc.CLIENT)

        def file_for(client_obj, passport_obj, dest, job, agent=None):
            existing = VisaCase.objects.filter(client=client_obj, passport=passport_obj).first()
            if existing:
                return existing
            return open_case(
                client=client_obj, passport=passport_obj, branch=branch, destination=dest,
                visa_category="Work", job_title=job, agent=agent, officer=officer, user=alice,
            )

        # Paid, medically live, issued KSA electrician
        ksa = file_for(c_karim, p_karim, "SAU", "Electrician")
        if ksa.stage == VisaCase.Stage.SIGN:
            advance_case(ksa, VisaCase.Stage.DOCS, user=alice)
            CaseDocument.objects.get_or_create(case=ksa, kind="Passport bio",
                                               defaults={"filename": "karim-bio.pdf", "status": "ok"})
            CaseDocument.objects.get_or_create(case=ksa, kind="NID",
                                               defaults={"filename": "karim-nid.pdf", "status": "ok"})
            advance_case(ksa, VisaCase.Stage.ATTEST, user=alice)
            Attestation.objects.get_or_create(case=ksa, certificate="SSC", authority="MOFA",
                                              defaults={"order": 1, "cleared": True, "gov_fee": Decimal("850")})
            Attestation.objects.get_or_create(case=ksa, certificate="SSC", authority="KSA Embassy",
                                              defaults={"order": 2, "cleared": True, "gov_fee": Decimal("2400")})
            advance_case(ksa, VisaCase.Stage.MED_SCHED, user=alice)
            record_medical(ksa, result="fit", clinic="Gulf Diagnostic, Banani", slip="WAF-88421",
                           issued_on=today)
            ksa.refresh_from_db()
            PortalSubmission.objects.get_or_create(case=ksa, portal="Qiwa",
                                                   defaults={"application_no": "QI-2026-10021",
                                                             "sponsor": "Al Noor Contracting",
                                                             "status_raw": "Iqama issued",
                                                             "submitted_on": timezone.now()})
            if not ksa.invoices.exists():
                inv = raise_invoice(case=ksa, amount=Decimal("85000"), tax=Decimal("0"),
                                    description="KSA work visa package", user=alice)
                take_receipt(invoice=inv, amount=Decimal("85000"), method="bkash",
                             reference="BKash9X21", staff=officer, user=alice)
            advance_case(ksa, VisaCase.Stage.PORTAL, user=alice)
            advance_case(ksa, VisaCase.Stage.EMBASSY, user=alice)
            advance_case(ksa, VisaCase.Stage.ISSUED, user=alice)

        # Live UAE welder — FIT with 10 days left (inside 30-day alert)
        uae = file_for(c_nabil, p_nabil, "ARE", "Welder", agent=agent_ok)
        if uae.stage == VisaCase.Stage.SIGN:
            advance_case(uae, VisaCase.Stage.DOCS, user=alice)
            advance_case(uae, VisaCase.Stage.MED_SCHED, user=alice)
            record_medical(uae, result="fit", clinic="Wafid Panel, Uttara", slip="WAF-11002",
                           issued_on=today - timedelta(days=50))
            if not uae.invoices.exists():
                inv = raise_invoice(case=uae, amount=Decimal("72000"), description="UAE work visa",
                                    user=alice)
                take_receipt(invoice=inv, amount=Decimal("30000"), method="cash", staff=officer, user=alice)
            PortalSubmission.objects.get_or_create(case=uae, portal="MOHRE",
                                                   defaults={"application_no": "MH-7781",
                                                             "sponsor": "Desert Steel LLC",
                                                             "status_raw": "Pending medical",
                                                             "submitted_on": timezone.now()})

        # Rangpur agent over credit — unpaid, locked, pouch hidden
        qat = file_for(c_rafiq, p_rafiq, "QAT", "Heavy driver", agent=agent_lock)
        if qat.stage == VisaCase.Stage.SIGN:
            advance_case(qat, VisaCase.Stage.DOCS, user=alice)
            advance_case(qat, VisaCase.Stage.MED_SCHED, user=alice)
            record_medical(qat, result="fit", clinic="Qatar Medical, Dhanmondi", slip="WAF-33001",
                           issued_on=today - timedelta(days=56))
            if not qat.invoices.exists():
                raise_invoice(case=qat, amount=Decimal("90000"), description="Qatar work visa",
                              user=alice)
            PortalSubmission.objects.get_or_create(case=qat, portal="Metrash2",
                                                   defaults={"application_no": "MT-4401",
                                                             "sponsor": "Gulf Logistics WLL",
                                                             "status_raw": "Returned — medical window",
                                                             "submitted_on": timezone.now()})

        Lead.objects.get_or_create(phone="01719990001",
                                   defaults={"name": "Jamal Sheikh", "destination": "KWT",
                                             "visa_category": "Work", "source": "facebook",
                                             "note": "Wants PAM domestic slot"})
        Lead.objects.get_or_create(phone="01719990002",
                                   defaults={"name": "Farhana Islam", "destination": "MYS",
                                             "visa_category": "Student", "source": "walk-in"})

        if not officer.attendance.filter(day=today).exists():
            clock_in(officer)
        if not officer.leaves.exists():
            request_leave(officer, today + timedelta(days=10), today + timedelta(days=12),
                          reason="Family visit")
        if not officer.payrolls.exists():
            run_payroll(officer, today.strftime("%Y-%m"), housing=Decimal("5000"),
                        transport=Decimal("3000"))

        if not branch.petty.exists():
            petty_out(branch=branch, staff=officer, amount=Decimal("1800"),
                      purpose="Wafid slip printing", expense_code="5020", user=alice)
            petty_out(branch=branch, staff=officer, amount=Decimal("650"),
                      purpose="MOFA courier", expense_code="5030", user=alice)

        from core.models import Invoice, Medical
        from core.services import trial_balance
        self.stdout.write(self.style.SUCCESS(
            f"Trust Overseas seeded: {Client.objects.count()} clients, "
            f"{VisaCase.objects.count()} files, {Invoice.objects.count()} invoices, "
            f"{Medical.objects.count()} medicals, trial balance ৳ {trial_balance()}. "
            f"Demo alice / DemoPass123!  ·  client karim / DemoPass123!  ·  agent hasan / DemoPass123!"
        ))
        # silence unused
        _ = (ZERO, p_sadia)
