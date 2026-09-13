# Trust Overseas Ltd

> **Visa & recruitment ERP** — cases, GAMCA/Wafid, passport vault, GCC portals, double-entry, petty cash, HR.

A sellable agency operating system for a Dhaka recruiting house. Every visa file is a stage machine, a custody chain and a journal — not a WhatsApp thread.

## What you get

- **Public site** — destinations (KSA, UAE, Qatar, Kuwait, Bahrain, Oman, Malaysia), enquire form, PIN tracking
- **Client portal** — files, invoices, visa-pouch download (locked while unpaid)
- **B2B agent desk** — sub-agent files with a credit hard-stop that hides pouch barcodes
- **Staff ERP**
  - CRM: leads, clients, KYC, sub-agents
  - Passport vault with custody events (unpaid files never return to the client)
  - Case machine: inquiry → docs → attestation → medical → Qiwa/Enjaz/MOHRE/Metrash2/PAM → embassy → issued → flight
  - GAMCA/Wafid board: FIT certificates expire in **60 days**; embassy submit locks under **5 days** remaining
  - **190-day** passport halt (and two blank pages)
  - Double-entry ledger: advances sit in **unearned retainers (2010)** until the visa is issued
  - Petty cash, trial balance, chart of accounts, audit log
  - HR: clock, leave (no overlaps), payroll

## Quickstart (Python 3.10+)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # then fill in DJANGO_SECRET_KEY
python manage.py migrate
python manage.py seed_demo
python manage.py runserver       # http://127.0.0.1:8000
```

Demo logins (after `seed_demo`):

| Who | Username | Password |
|---|---|---|
| Case manager | `alice` | `DemoPass123!` |
| Client | `karim` | `DemoPass123!` |
| Sub-agent | `hasan` | `DemoPass123!` |
| Superuser | `admin` | `admin` |

Public track: Karim Mia’s PIN is `123456`.

```bash
python manage.py test
python manage.py check --deploy  # DJANGO_DEBUG=False + a real secret
```

## Guards that keep a file honest

1. Passport remaining life **< 190 days** blocks case opening.
2. GAMCA/Wafid FIT **expires in 60 days**; embassy / portal submit is locked under **5 days**.
3. Sub-agent **credit hard-stop** hides downloads and pouch barcodes.
4. **Unpaid invoice** locks visa PDF / pouch release and keeps the booklet in the vault.
5. Every money movement is a balanced journal pair. Trial balance is **৳ 0.00**.
6. Advances sit in account **2010 Unearned retainers** until the visa is issued (then **4010**).

## Tech stack

- **Django 5.2 LTS** (Python 3.10–3.13), SQLite out of the box, PostgreSQL-ready
- First-party HTML/CSS frontend, no CDN, no build step
- Argon2 password hashing, CSP + nonce, HSTS/secure-cookie flags via `.env`,
  login brute-force throttling, CSRF everywhere

## Deploy

See **[docs/DEPLOY.md](docs/DEPLOY.md)**. Dockerfile, Procfile and `render.yaml` are in the repo.

## Layout

```
30-trustoverseas/
├── manage.py
├── config/            settings · root urls · wsgi/asgi
├── core/              models · services · views · forms · admin · tests
├── templates/trust/   public site, portals, staff desk
├── static/css/        first-party stylesheet (navy + gold)
└── docs/DEPLOY.md
```
