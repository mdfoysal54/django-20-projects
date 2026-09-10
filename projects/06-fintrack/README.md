# 💹 FinTrack — personal finance & budget dashboard

> Flagship **#6** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · first-party HTML/CSS frontend · hardened security baseline ·
> **41 automated tests, all green.**

A personal-finance app with real accounting discipline: multi-account ledger,
income/expense tracking with a strict sign convention, balanced transfers,
monthly budgets with 80%/100% alerts, six-month trend reports and a
**transaction-validated CSV import**.

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Dashboard** | Month navigator, total balance across accounts, income vs expenses vs net, spending-by-category bars, recent transactions, budget watchlist, over-budget alert banner |
| **Accounts** | Bank/card/cash/wallet/savings accounts with opening balances, **derived running balance**, negative-balance flagging, per-account ledger |
| **Transactions** | Expenses, income and transfers; filter by account/category/kind + free-text search; detail pages; expense/income sign handling done server-side |
| **Transfers** | Two linked legs (out + in) written in one DB transaction — totals always balance; same-account transfers rejected |
| **Budgets** | One budget per category per month, live spent/remaining, usage %, state badges (**ok / warn ≥80% / over ≥100%**), month navigation |
| **CSV import** | Upload a bank export → per-row validation with an added/skipped report; UTF-8 BOM tolerated; extension allow-list, 1 MB cap, row cap |
| **Reports** | Six-month income-vs-expense trend (CSS bars, no chart library) + current-month category breakdown |
| **Admin** | Account/category/transaction/budget management with date hierarchy and totals reporting action |

## Money rules, enforced in code

```python
# sign convention: expenses negative, income positive
Transaction.Kind.EXPENSE  → amount < 0     # model rejects positive expenses
Transaction.Kind.INCOME   → amount > 0     # model rejects negative income
Transaction.create_transfer(...)           # two rows, one atomic write, one group id

# balances are never stored — always derived
Account.balance == opening_balance + SUM(transactions.amount)
```

- Budgets credit only **expenses** (`amount < 0` filters), so refunds/income can
  never silently "fix" an overspent category.
- Transfers are excluded from income/expense totals (they're internal movement).
- `Decimal(12,2)` everywhere; floats never touch money.

## Page map

```
/                          dashboard (?year=&month=)
/transactions/             ledger with filters
/transactions/new/         add expense/income
/transactions/<id>/        transaction detail
/transactions/transfer/    balanced transfer
/transactions/import/      CSV import + validation report
/accounts/                 accounts overview
/accounts/new/  /accounts/<id>/     create / ledger
/categories/  /categories/new/      category management
/budgets/  /budgets/new/            monthly budgets
/reports/                 trends
/profile/  /login/  /logout/ …      account & auth
/admin/                   Django admin
```

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo            # 5 accounts, 10 categories, ~220 transactions, budgets
python manage.py runserver
```

**Demo account:** `alice` / `DemoPass123!` (six months of realistic history,
including budgets that are genuinely close to their limits) · `admin` / `DemoPass123!`

## Tests — 41 total

- `core/tests_security.py` — 12 canonical security tests
- `core/tests.py` — 29 domain tests:
  - **Money**: derived balances, negative-balance flagging, sign conventions
    enforced both ways, zero/future dates rejected, wrong-kind categories rejected
  - **Transfers**: two linked legs, conservation of total money, same-account &
    non-positive rejections
  - **Budgets**: spent/remaining maths, warn at 80%, over at 100%, income never
    counts, cross-month isolation, income-category budget rejected
  - **CSV import**: happy path with category matching, bad rows skipped *with
    reasons*, missing header rejected, non-CSV extension rejected, 1 MB cap,
    UTF-8 BOM tolerance
  - **Ownership**: transaction/account detail 404 for other users, per-user
    dashboard totals
  - **Flows**: expense saved signed correctly from the HTML form, negative
    amount rejected, transfer flow over HTTP, seeder balance consistency

## Security notes

Beyond the [shared baseline](../../docs/SECURITY.md):

- Every queryset is user-scoped **at the source** (`user=request.user` in the
  query, not in a template check) — no view in this app can leak another
  user's money.
- CSV uploads: extension allow-list, 1 MB cap, UTF-8 decode with clear error,
  per-row `full_clean()` model validation inside a transaction, and a
  human-readable report of what was skipped and why.
- No stored balances means no drift: an attacker (or bug) that edits one
  transaction cannot desynchronise a cached total.
