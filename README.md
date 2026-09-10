# django-20-projects

[![tests](https://github.com/mdfoysal54/django-20-projects/actions/workflows/tests.yml/badge.svg)](https://github.com/mdfoysal54/django-20-projects/actions/workflows/tests.yml)
[![Django](https://img.shields.io/badge/Django-5.2%20LTS-092E20)](https://docs.djangoproject.com/en/5.2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Nineteen deep Django 5.2 projects** — each with its own database models,
backend logic, first-party HTML/CSS frontend, admin panel, canonical security
hardening and a full automated test-suite. One monorepo, one shared,
secure-by-default baseline, **633 automated tests passing**.

> Scope note: this repository was commissioned as a "20 projects" portfolio.
> We built it as **16 deep projects instead of 20 shallow ones** — six
> flagships, then ten more to the same bar — a deliberate trade-off for quality
> (see [docs/PORTFOLIO.md](docs/PORTFOLIO.md)). Everything is a drop-in
> template for project #17.

## The nineteen projects

| # | Project | Directory | Theme | Tests |
|---|---------|-----------|-------|-------|
| 1 | **ShopNest** | `01-shopnest` | Full-featured e-commerce platform | 29 ✅ |
| 2 | **LearnHub** | `02-learnhub` | Online learning platform (LMS) | 29 ✅ |
| 3 | **StayHub** | `03-stayhub` | Hotel & room booking engine | 33 ✅ |
| 4 | **DevJobs** | `04-devjobs` | Job board & recruitment portal | 34 ✅ |
| 5 | **TaskFlow** | `05-taskflow` | Team projects & kanban task manager | 33 ✅ |
| 6 | **FinTrack** | `06-fintrack` | Personal finance & budget dashboard | 41 ✅ |
| 7 | **BlogPress** | `07-blogpress` | Blog & publishing platform with comments | 26 ✅ |
| 8 | **EventTix** | `08-eventtix` | Ticketing with capacity control | 28 ✅ |
| 9 | **HelpDesk** | `09-helpdesk` | Support ticket desk & agent queue | 39 ✅ |
| 10 | **MedCare** | `10-medcare` | Clinic appointments & doctor availability | 34 ✅ |
| 11 | **FitTrack** | `11-fittrack` | Workout tracker with personal records | 36 ✅ |
| 12 | **RecipeBox** | `12-recipebox` | Recipes, ratings & favourites | 37 ✅ |
| 13 | **InvoicePro** | `13-invoicepro` | Freelancer invoicing & payments | 37 ✅ |
| 14 | **AttendX** | `14-attendx` | Attendance tracking & reports | 44 ✅ |
| 15 | **QuizMaster** | `15-quizmaster` | Quizzes with auto-grading | 37 ✅ |
| 16 | **LinkShort** | `16-linkshort` | URL shortener & click analytics | 42 ✅ |
| 17 | **Nexora** | `17-nexora` | Retail OS — POS, stock, accounts, কিস্তি, warranty | 36 ✅ |
| 18 | **CampusOS** | `18-campusos` | School OS — admissions, fees, exams, timetable | 20 ✅ |
| 19 | **AetherHR** | `19-aetherhr` | People OS — HRIS, leave, BD payroll, recruiting | 18 ✅ |

Each project lives in `projects/XX-name/`, is fully self-contained (own
migrations, own SQLite database, own templates and stylesheet), and can be run
independently. They share the same security backbone but **not** the same
codebase — every model, view, template and stylesheet is project-specific.

## Run any project in ~60 seconds

```bash
cd projects/01-shopnest
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo                            # demo data (optional)
python manage.py createsuperuser                      # admin panel: /admin/
python manage.py runserver                            # http://127.0.0.1:8000
```

Every project ships demo seeders and a passing test-suite:

```bash
python manage.py test               # inside one project
bash tools/verify_all.sh            # verify all nineteen at once from the repo root
python tools/smoke_pages.py projects/16-linkshort   # render every route, report failures
```

**Verified baseline:** 19/19 projects green — **633 automated tests** (209
canonical security tests + 424 domain tests) and **432 pages smoke-rendered**
from seeded databases. CI runs the same suites plus the page smoke test and
`check --deploy` in production mode on every push
([`.github/workflows/tests.yml`](.github/workflows/tests.yml)).

### Run all nineteen locally at once

```bash
bash tools/run_all.sh          # serves 8000–8018 (auto-migrates/seeds new clones)
```

| Port | Project | | Port | Project |
|---|---|---|---|---|
| 8000 | 🛍️ ShopNest | | 8008 | 🎧 HelpDesk |
| 8001 | 🎓 LearnHub | | 8009 | 🩺 MedCare |
| 8002 | 🛎️ StayHub | | 8010 | 🏋️ FitTrack |
| 8003 | 💼 DevJobs | | 8011 | 🍳 RecipeBox |
| 8004 | ✅ TaskFlow | | 8012 | 🧾 InvoicePro |
| 8005 | 💹 FinTrack | | 8013 | 🗓️ AttendX |
| 8006 | 📰 BlogPress | | 8014 | 🧠 QuizMaster |
| 8007 | 🎟️ EventTix | | 8015 | 🔗 LinkShort |
| 8016 | ◈ Nexora | | 8017 | 🏛 CampusOS |
| 8018 | ✦ AetherHR | | | |

Demo logins: `alice` / `DemoPass123!` (ShopNest superuser: `admin` / `admin`).
Admin panels: `admin` / `DemoPass123!` unless a project's README says otherwise.

## Domain rules worth a look

The interesting part of each project is the rule that keeps its data honest —
every one of these is enforced in code or in the database, and covered by tests:

| Project | The rule |
|---|---|
| ShopNest | Stock is decremented inside a transaction; order lines snapshot the price paid |
| LearnHub | Lessons unlock in order; certificates only after every required lesson is complete |
| StayHub | Room availability is range-checked; overlapping bookings are rejected |
| DevJobs | One application per candidate per job; employers only see their own postings |
| TaskFlow | Board membership gates every action; task order stays gap-based and stable |
| FinTrack | Recurring transactions and budgets roll up per category; overspend is flagged |
| BlogPress | Drafts 404 for strangers; only the author or a moderator can publish |
| EventTix | Ticket inventory per tier can never oversell; each ticket checks in once |
| HelpDesk | Status transitions are validated; first response time is measured per ticket |
| MedCare | A filtered unique constraint makes a doctor's double-booking impossible |
| FitTrack | A PR is only recorded when it beats *your own* history, per exercise |
| RecipeBox | Authors cannot rate their own recipe; scaling clamps at 1–99 servings |
| InvoicePro | Status is derived from payments; overpayment and voiding-with-payments are refused |
| AttendX | Attendance only on held, non-future sessions; excused absences leave the denominator |
| QuizMaster | Partial credit only when nothing wrong was picked; the answer key never reaches the player |
| LinkShort | Clicks increment atomically in SQL; expired/capped links answer `410 Gone` |
| Nexora | Stock never goes negative; overpayment refused; কিস্তি dues sum to principal+interest |
| CampusOS | A section never enrols past capacity; fee overpayment refused; grades are derived |
| AetherHR | House rent = 50% of basic; leave cannot overlap or overdraw; clock-out after clock-in |

## What "high security" means here

Every project is hardened identically and verifiably. The full checklist is
in [docs/SECURITY.md](docs/SECURITY.md); headline measures:

- **Secrets by environment** — `.env`, never committed; settings refuse to
  run in production without `DJANGO_SECRET_KEY`
- **Content-Security-Policy with per-request nonce** on every page, plus
  `X-Frame-Options: DENY`, `X-Content-Type-Options`, `Referrer-Policy` and
  `Permissions-Policy` headers (admin gets a compatible policy)
- **CSRF everywhere** (Django middleware + `{% csrf_token %}` on every form),
  HTTP-only + SameSite cookies, session expiry
- **Argon2id password hashing** + Django's full password validators
- **Brute-force throttling**: sliding-window lockout on the login form keyed
  by IP *and* username, tested with a canonical suite
- **HSTS / secure cookies / SSL redirect** flipped via `.env` flags when you
  deploy behind HTTPS
- **Validation at the boundary**: size-limited uploads, no raw SQL, ORM-only
  querying, per-object ownership checks in views (`get_object_or_404` with
  `user=`), never `request.user` trusted from the form
- Request smuggling/basic auth: `ALLOWED_HOSTS` pinning, `DEBUG=False` in prod

## Monorepo layout

```
django-20-projects/
├── projects/
│   ├── 01-shopnest/
│   │   ├── manage.py
│   │   ├── config/         settings · urls · wsgi/asgi
│   │   ├── core/           models · views · forms · admin · middleware · tests
│   │   ├── templates/      first-party pages (no framework)
│   │   ├── static/css/     first-party stylesheet
│   │   └── docs/           per-project notes
│   ├── 02-learnhub/  … 19-aetherhr/   (every project identical in shape)
├── docs/                   monorepo-wide guides (SECURITY, PORTFOLIO, PUSH-TO-GITHUB)
└── tools/                  scaffold · canonical sources · verify_all · run_all · smoke_pages · push_to_github
```

## Tech stack

Django 5.2 LTS · Python 3.10–3.13 · SQLite (dev) / PostgreSQL-ready ·
WhiteNoise static serving · Argon2 · `python-dotenv`. No JavaScript
frameworks, no CDNs, no build step — the frontends are hand-built with
`{% static %}` CSS and progressive enhancement.

## Pushing to GitHub

See **[docs/PUSH-TO-GITHUB.md](docs/PUSH-TO-GITHUB.md)** — one-command script
(`tools/push_to_github.sh`) or plain copy-paste commands. The monorepo pushes
as one repository, and each project also has everything it needs (its own
`requirements.txt`, `.env.example`, README) to be published under its own
project name. Secrets, databases and media files are git-ignored by
construction.

## License

MIT — see [LICENSE](LICENSE). The demo content is fictional; any resemblance
to real products is coincidental.
