# Why deep projects instead of shallow ones

The commission was "20 Python/Django projects", then more. We kept trading
breadth for depth: six flagships, ten more to the same bar, three sellable
operating systems, then **ten distinct deployable websites**. Twenty-nine
complete, hardened, tested products beat a pile of half-built clones.

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
| Wave 3 | 17 Nexora · 18 CampusOS · 19 AetherHR | Retail OS, school OS, people OS — sellable products |
| Wave 4 | 20 TideTable · 21 Parcelio · 22 AuroraRealty · 23 Salonova · 24 VaultSign | Restaurant, courier, property, salon, e-sign |
| Wave 4 | 25 CivicPulse · 26 FleetNova · 27 OrbitPay · 28 PulseGrid · 29 Lexora | Civic, fleet, wallet, SRE, legal practice |

Verified baseline: **29/29 green — 797 automated tests** (319 canonical
security + 478 domain) plus **553 pages smoke-rendered** from a seeded database.

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
- **Nexora** — stock never goes negative; transfers conserve quantity; POS
  overpayment is refused; কিস্তি dues sum exactly to principal + interest.
- **CampusOS** — a section never enrols past capacity; fee overpayment is
  refused; exam grades are derived from marks; library loans cannot over-issue.
- **AetherHR** — house rent is 50% of basic; leave cannot overlap or overdraw;
  clock-out cannot precede clock-in; unpaid days prorate against a 30-day month.
- **TideTable** — a table never takes a party larger than its seats; two covers
  cannot share a 90-minute window.
- **Parcelio** — last-mile parcels cap at 30 kg; out-for-delivery needs a courier.
- **AuroraRealty** — offers below 80% of asking are refused; accepting one offer
  sells the listing and declines the rest.
- **VaultSign** — completed envelopes are immutable; only listed emails can sign.
- **OrbitPay** — every send is two ledger entries; voids reverse both sides.
- **Lexora** — time is billed in six-minute slices; closed matters refuse time.

## Scaling further is a copy job, not a rewrite

Everything shared lives in `tools/canonical*.py`. To spin up project #20:

```bash
# 1. add an entry to tools/canonical.PROJECTS
# 2. regenerate the skeleton
python tools/scaffold.py
# 3. build the domain: core/models.py → forms → views → urls → templates → tests
python ../tools/smoke_pages.py .   # every route renders
```

A new project immediately inherits the CSP/nonce middleware, login throttling,
hardened settings, branded error pages, auth templates and the canonical
security suite. The twenty-nine projects here show how to finish the job properly.
