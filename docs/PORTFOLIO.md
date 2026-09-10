# Why 16 deep projects instead of 20 shallow ones

The commission was "20 Python/Django projects", later expanded to *sixteen
genuinely finished applications*: six flagships first, then ten more built to
exactly the same bar. We deliberately traded breadth for depth — sixteen
complete, hardened, tested products beat twenty half-built clones, for a
portfolio, for learning, and for an interview walkthrough.

Nothing here is a tutorial clone. Each project owns its domain model, its
invariants, its tests and its frontend.

## What every project includes

| Layer | Depth |
|---|---|
| Database | 4–8 related models per app, real constraints (unique, check, filtered unique), migrations |
| Backend | Auth flows, per-object ownership checks, transactions and row locking, derived state, demo seeders |
| Frontend | 8–12 hand-built pages per app, responsive first-party CSS, CSP-safe progressive JS |
| Security | Shared verified baseline (see SECURITY.md) + domain-specific guards |
| Tests | 26–44 automated tests per app (11 canonical security + 15–33 domain edge cases) |
| Docs | Per-project README: features, page map, data model, deploy guide |

## What shipped

| Wave | Projects | Theme |
|---|---|---|
| Flagships | 01 ShopNest · 02 LearnHub · 03 StayHub · 04 DevJobs · 05 TaskFlow · 06 FinTrack | Commerce, learning, travel, hiring, teamwork, finance |
| Wave 2 | 07 BlogPress · 08 EventTix · 09 HelpDesk · 10 MedCare · 11 FitTrack | Publishing, ticketing, support, clinics, fitness |
| Wave 2 | 12 RecipeBox · 13 InvoicePro · 14 AttendX · 15 QuizMaster · 16 LinkShort | Recipes, invoicing, attendance, quizzes, link analytics |

Verified baseline: **16/16 green — 559 automated tests** (176 canonical
security + 383 domain) plus **291 pages smoke-rendered** from a seeded database.

Depth per project is not decoration. Examples of rules that are enforced in the
database or in guarded model methods, and covered by tests:

- **EventTix** — ticket inventory per tier, check-in once per ticket, bookings
  refuse to oversell even under concurrent requests.
- **MedCare** — a filtered `UniqueConstraint` makes double-booking a doctor's
  slot impossible at the database level; a second guard stops one patient
  booking two appointments in the same slot.
- **InvoicePro** — status is always derived from payments, overpayment is
  refused, invoice numbers are sequential per year, and voiding is blocked once
  money has landed.
- **AttendX** — attendance can only be marked on held, non-future sessions;
  excused absences leave the denominator instead of counting as failures.
- **QuizMaster** — multi-select answers earn partial credit only when nothing
  wrong was picked, one-attempt-only is enforced server-side, and the answer
  key is never sent to the player's page.
- **LinkShort** — click counts increment atomically in SQL, expired or capped
  links answer `410 Gone`, and only salted IP hashes are stored.

## Scaling further is a copy job, not a rewrite

Everything shared lives in `tools/canonical*.py`. To spin up project #17:

```bash
# 1. add an entry to tools/canonical.PROJECTS
# 2. regenerate the skeleton
python tools/scaffold.py
# 3. build the domain: core/models.py → forms → views → urls → templates → tests
python ../tools/smoke_pages.py .   # every route renders
```

A new project immediately inherits the CSP/nonce middleware, login throttling,
hardened settings, branded error pages, auth templates and the canonical
security suite. The sixteen projects here show how to finish the job properly.
