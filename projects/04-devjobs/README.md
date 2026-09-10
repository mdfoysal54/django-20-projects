# 💼 DevJobs — job board & recruitment portal

> Flagship **#4** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · first-party HTML/CSS frontend · hardened security baseline ·
> **34 automated tests, all green.**

A two-sided job board: candidates search, save and apply to roles with resume
uploads; employers manage company profiles, post jobs and move applicants
through a real hiring pipeline (submitted → review → shortlisted → interview →
offer → hired / rejected).

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Job search** | Keyword search across title/description/tags/company, location, job type, level and workplace (remote/hybrid/on-site) filters, three sort orders, expired jobs auto-hidden |
| **Job pages** | Transparent salary display (range / single+ / not disclosed), requirement lists, skill tags, similar roles from the same company, deadline countdown |
| **Applying** | Login-gated, one application per job (view check **and** DB unique constraint), cover-letter quality gate, resume upload with extension allow-list + 2 MB cap, optional portfolio |
| **Candidate area** | Application tracker with live pipeline badges, one-click withdraw (POST + CSRF, owner-only), saved-jobs shortlist with toggle |
| **Employer area** | Company profiles, create/edit jobs, open/close toggle, applicant list with resumes, per-candidate review page with pipeline status + **private** employer notes |
| **Admin** | Company inline job editing, job bulk open/close, application bulk status actions, resume flag column |

## Page map

```
/                                    home (search hero, stats, companies hiring)
/jobs/                               job list with filters (?q=&location=&job_type=&level=&remote=&sort=)
/jobs/<slug>/                        job detail (apply / already-applied / owner states)
/jobs/<slug>/apply/                  application form (login required)
/jobs/<slug>/save/                   POST toggle save-for-later
/companies/<slug>/                   public company page
/my-applications/                    candidate tracker
/applications/<id>/withdraw/         POST withdraw
/saved-jobs/                         shortlist
/employer/                           dashboard (own jobs only, new-applicant counts)
/employer/company/new/               create company
/employer/jobs/new/                  post a job
/employer/jobs/<slug>/edit/          edit / close / re-open
/employer/jobs/<slug>/applicants/    applicant list
/employer/applications/<id>/review/  pipeline status + private notes
/profile/  /accounts/*  /admin/      account & admin
```

## Data model

```
User ──< Company ──< Job ──< Application >── User
        (owner)      (posted_by)     │  unique (job, applicant)
                                     └── status · resume · employer_notes
User ──< SavedJob >── Job
```

- `unique_together("job", "applicant")` makes "apply once" a database law, not
  just a view check.
- Applications are never deleted — `withdraw()` is the only candidate-side
  transition, so an employer's pipeline history stays truthful.
- Salary inputs are validated (`min ≤ max`), deadlines can't be in the past.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo            # 4 companies, 9 jobs, demo applications
python manage.py runserver
```

**Demo accounts**

| Username | Password | Role |
|---|---|---|
| `nadia` | `DemoPass123!` | recruiter — Nimbus Cloud & BlueOrbit Labs |
| `tanvir` | `DemoPass123!` | recruiter — Pixel & Pine & The Ledger Co |
| `alice` | `DemoPass123!` | candidate — 2 applications (interview / shortlisted) |
| `bob` | `DemoPass123!` | candidate — 2 applications (submitted / reviewing) |
| `admin` | `DemoPass123!` | superuser |

## Tests — 34 total

- `core/tests_security.py` — 12 canonical security tests
- `core/tests.py` — 22 domain tests: salary display variants, min>max
  rejection, expired/draft visibility, deadline enforcement, keyword +
  filter search, apply-once, short cover letters, recruiter-can't-apply-to-own-job,
  resume happy path, **extension blocklist (`.exe` rejected)**, **2 MB size cap**,
  withdraw + no-reapply, cross-user protection on applications, employer
  scoping (strangers get 404 on applicants and review pages), pipeline moves,
  open/close toggling, saved-job toggling, seeder integrity

## Security notes

Beyond the [shared baseline](../../docs/SECURITY.md):

- **Upload hardening**: resumes are extension-allow-listed (pdf/doc/docx/txt/rtf/odt),
  capped at 2 MB, and stored with the client filename reduced to its basename
  (`Path(name).name`) so no path traversal reaches the storage layer.
- Candidate data (cover letters, resumes, email) is visible only to the job's
  poster and admins — verified by tests that log in as a stranger and expect 404s.
- Company selection on job creation is validated against `owner=request.user`;
  a tampered `company` pk in the POST body cannot cross tenants.
