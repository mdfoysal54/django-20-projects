# AetherHR

> **People operating system — HRIS, attendance, leave, payroll, performance** — flagship Django project in the **django-20-projects** monorepo.

A complete HR desk you can sell and deploy: directory + org chart, clock in/out, leave that cannot overlap or overdraw, Bangladesh payroll (basic + 50% house rent + medical + conveyance, unpaid days prorated on a 30-day month), recruiting pipeline, reviews, assets, announcements, language/colour.

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

- Clock in once per day; clock out cannot precede clock in.
- Leave windows cannot overlap; remaining balance is deducted only on approval.
- House rent = 50% of basic. Net = gross − (gross/30 × unpaid days).

Django 5.2 LTS · first-party HTML/CSS · Argon2 · CSP + nonce.
