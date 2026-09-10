# CampusOS

> **School operating system — admissions, fees, exams, timetable, parent portal** — flagship Django project in the **django-20-projects** monorepo.

A complete campus desk you can sell and deploy: students and guardians, capacity-safe enrolment, fee invoices (no overpayment), attendance registers (excused leave the denominator), auto-graded exams, timetable, library loans that cannot over-issue, transport, notices, SMS log, language/colour.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Demo: `alice` / `DemoPass123!`  ·  admin: `admin` / `admin`

## Domain rules

- A section never enrols past its capacity.
- Fee overpayment is refused; status is derived from payments.
- Attendance rate = (present + late) / (total − excused).
- Exam marks clamp to the paper; grades A+…F are derived.
- Library loans refuse a book that is not on the shelf.

Django 5.2 LTS · first-party HTML/CSS · Argon2 · CSP + nonce.
