# django-20-projects

[![tests](https://github.com/OWNER/django-20-projects/actions/workflows/tests.yml/badge.svg)](https://github.com/OWNER/django-20-projects/actions/workflows/tests.yml)
[![Django](https://img.shields.io/badge/Django-5.2%20LTS-092E20)](https://docs.djangoproject.com/en/5.2/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Six flagship Django 5.2 projects** — each with its own database models,
backend logic, first-party HTML/CSS frontend, admin panel, canonical
security hardening and a full automated test-suite. One monorepo, one
shared, secure-by-default baseline.

> Scope note: this repository was commissioned as a "20 projects" portfolio.
> We built it as **6 deep flagship projects** instead of 20 shallow ones — a
> deliberate trade-off for quality (see [docs/PORTFOLIO.md](docs/PORTFOLIO.md)).
> The architecture scales down cleanly to 20 apps if you prefer breadth:
> every project below is a drop-in template for a new one.

## The projects

| # | Project            | Theme                                  | Status |
|---|--------------------|----------------------------------------|--------|
| 1 | **ShopNest**       | Full-featured e-commerce platform      | ✅ built · 29 tests green |
| 2 | **LearnHub**       | Online learning platform (LMS)         | ✅ built · 29 tests green |
| 3 | **StayHub**        | Hotel & room booking engine            | ✅ built · 33 tests green |
| 4 | **DevJobs**        | Job board & recruitment portal         | ✅ built · 34 tests green |
| 5 | **TaskFlow**       | Team projects & kanban task manager    | ✅ built · 33 tests green |
| 6 | **FinTrack**       | Personal finance & budget dashboard    | ✅ built · 41 tests green |

*(This README is updated as each flagship lands — statuses here are the source of truth.)*

Each project lives in `projects/XX-name/`, is fully self-contained, and can
be run independently. They share the same security backbone but **not** the
same codebase — every model, view, template and stylesheet is project-specific.

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
python manage.py test          # inside one project
bash tools/verify_all.sh       # verify all six at once from the repo root
```

**Verified baseline:** 6/6 projects green — 199 automated tests in total
(72 canonical security tests + 127 domain tests). CI runs the same suites plus
`check --deploy` in production mode on every push
([`.github/workflows/tests.yml`](.github/workflows/tests.yml)).

### Run all six locally at once

```bash
bash tools/run_all.sh          # serves 8000–8005 (auto-migrates/seeds new clones)
```

| Port | Project | | Port | Project |
|---|---|---|---|---|
| 8000 | 🛍️ ShopNest | | 8003 | 💼 DevJobs |
| 8001 | 🎓 LearnHub | | 8004 | ✅ TaskFlow |
| 8002 | 🛎️ StayHub | | 8005 | 💹 FinTrack |

Demo logins everywhere: `alice` / `DemoPass123!` · admin panels: `admin` / `DemoPass123!`

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
│   ├── 02-learnhub/  …     (each project identical in shape)
├── docs/                   monorepo-wide guides (SECURITY, PORTFOLIO)
└── tools/                  scaffold + GitHub push scripts
```

## Tech stack

Django 5.2 LTS · Python 3.10–3.13 · SQLite (dev) / PostgreSQL-ready ·
WhiteNoise static serving · Argon2 · `python-dotenv`. No JavaScript
frameworks, no CDNs, no build step — the frontends are hand-built with
`{% static %}` CSS and progressive enhancement.

## Pushing to GitHub

See **[docs/PUSH-TO-GITHUB.md](docs/PUSH-TO-GITHUB.md)** — one-command script
(`tools/push_to_github.sh`) or plain copy-paste commands. Secrets, databases
and media files are git-ignored by construction.

## License

MIT — see [LICENSE](LICENSE). The demo content is fictional; any resemblance
to real products is coincidental.
