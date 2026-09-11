# FleetNova

> **Odometers never rewind. Vehicles and drivers cannot double-dispatch.** — flagship Django project in the **django-20-projects** monorepo.

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

- One open trip per vehicle and per driver.
- Start km ≥ odometer.
- End km ≥ start km.

Django 5.2 LTS · WhiteNoise · SQLite / PostgreSQL-ready · `check --deploy` clean.
