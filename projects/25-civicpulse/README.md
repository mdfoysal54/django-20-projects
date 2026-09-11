# CivicPulse

> **No resolve without a crew. One open work order at a time.** — flagship Django project in the **django-20-projects** monorepo.

A complete, deployable product: first-party UI, hardened Django 5.2, Argon2, CSP + nonce, tests, demo seeder. No CDN, no secrets in git.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate && python manage.py seed_demo
python manage.py runserver
```

Demo: `alice` / `DemoPass123!`  ·  admin: `admin` / `admin`

## Domain rules

- Resolve requires an open work order.
- One open work order per issue.
- Closed / duplicate issues cannot dispatch.

Django 5.2 LTS · WhiteNoise · SQLite / PostgreSQL-ready · `check --deploy` clean.
