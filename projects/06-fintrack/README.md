# FinTrack

> **Personal finance & budget dashboard** — flagship Django project in the **django-20-projects** monorepo.

*Status: scaffolded — this page will be replaced by the project walkthrough
as the app is built out.*

---

## Quickstart (needs Python 3.10+)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in DJANGO_SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver       # http://127.0.0.1:8000
```

Run the test-suite (43 canonical security + domain tests):

```bash
python manage.py test
```

## Tech stack

- **Django 5.2 LTS** (Python 3.10–3.13), SQLite out of the box, PostgreSQL-ready
- First-party HTML/CSS frontend, no CDN, no build step
- Argon2 password hashing, CSP + nonce, HSTS/secure-cookie flags via `.env`,
  login brute-force throttling, CSRF everywhere

## Repository layout

```
06-fintrack/
├── manage.py
├── config/            settings · root urls · wsgi/asgi
├── core/              models · views · forms · admin · middleware · tests
├── templates/         first-party pages
├── static/css/        first-party stylesheet
├── tests/             security + domain tests live in core/tests*.py
└── docs/              SECURITY.md — hardening checklist
```

## Security checklist

See **[/docs/SECURITY.md](../docs/SECURITY.md)** (monorepo-wide) and
`config/settings.py` for exactly which flags this project sets.
