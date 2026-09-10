# 🛍️ ShopNest — full-featured e-commerce platform

> Flagship **#1** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · SQLite → PostgreSQL-ready · first-party HTML/CSS frontend ·
> hardened security baseline · **29 automated tests, all green.**

A complete storefront: catalogue with categories & sorting, stock-aware cart,
transaction-safe checkout that can never oversell, order history with status
tracking, customer accounts and a fully configured Django admin.

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Storefront** | Hero landing, category tiles, featured & new-arrival rails, CSS-only category dropdown |
| **Catalogue** | Category pages, 4 sort orders (newest, price ↑/↓, name), stock badges (low-stock warnings, out-of-stock states), draft/published workflow |
| **Product pages** | Image or branded fallback tile, description, stock counter, quantity picker clamped to real stock, related products |
| **Cart** | Database-backed per-user cart (never tamperable cookies), add/merge duplicates, quantity updates, line removal, live totals |
| **Checkout** | Shipping form with validated phone/address, order summary, **`select_for_update` row locking so concurrent checkouts cannot oversell**, automatic stock decrement |
| **Orders** | Immutable price/name snapshots per line, owner-scoped order pages (strangers get 404), status pipeline *pending → paid → shipped → delivered / cancelled* with badges |
| **Accounts** | Register (unique emails), login throttling, password change, profile with recent orders |
| **Admin** | Product list-editing (price/stock inline), image previews, publish/unpublish actions, order inline lines, status actions, date hierarchy |

## Page map

```
/                              home (hero + categories + rails)
/shop/                         full catalogue (sortable)
/shop/category/<slug>/         category view
/product/<slug>/               product detail
/cart/                         cart (login required)
/checkout/                     checkout (login required)
/orders/                       my orders
/orders/<id>/                  order detail (owner-only)
/profile/                      account home
/accounts/login|register|...   auth flows
/admin/                        Django admin
```

## Data model

```
Category ──< Product ──< CartItem >── Cart ──(1:1) User
                │
                └──< OrderItem >── Order ──< User
                          │            └── status · totals · shipping snapshot
                          └── product_name/unit_price snapshots
```

- **Money is `Decimal` end-to-end** — floats are never used for prices.
- Orders snapshot product names & prices so history survives catalogue edits.
- Deleting a product keeps order lines intact (`SET_NULL` + snapshot fields).

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # dev defaults work as-is
python manage.py migrate
python manage.py seed_demo                            # 6 categories, 12 products, demo order
python manage.py createsuperuser
python manage.py runserver
```

**Demo accounts created by the seeder**

| Username | Password | Role |
|---|---|---|
| `admin` | `admin` | superuser (change immediately anywhere non-local) |
| `alice` | `DemoPass123!` | customer with a sample order |

Product images are generated as styled gradient PNGs by the seeder (no Pillow,
no internet needed) into `media/products/` — re-run `seed_demo` any time.

## Tests — 29 total

```bash
python manage.py test
```

- `core/tests_security.py` — 12 canonical security tests (CSP + nonces, headers,
  CSRF tokens, registration rules, login throttle incl. per-IP/per-username keys)
- `core/tests.py` — 17 domain tests: catalogue visibility, draft hiding, cart
  merging/clamping, cross-user cart isolation (IDOR), full order flow, oversell
  prevention, owner-only order access, phone validation, seeder integrity

## Security highlights (see [/docs/SECURITY.md](../../docs/SECURITY.md))

- CSP with per-request nonce on every page; inline scripts are nonce-approved
  (the sort dropdown is the only JS on the site — 3 lines).
- Login brute-force lockout: 5 failed attempts per IP **and** per username → 429.
- Every view that touches user data is ownership-scoped; the checkout service
  re-validates stock under row locks inside a transaction.
- `python manage.py check --deploy` passes once the `.env` production flags are set.

## Deploying for real

1. `DJANGO_DEBUG=False`, real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=yourdomain`
2. Switch to PostgreSQL (see comment in `config/settings.py`), `pip install "psycopg[binary]"`
3. `DJANGO_SECURE_SSL_REDIRECT=True DJANGO_COOKIE_SECURE=True DJANGO_HSTS=True`
4. `python manage.py collectstatic` (WhiteNoise serves the hashed assets)
5. Run under gunicorn/uwsgi behind nginx or a PAAS — three commands, no surprises.
