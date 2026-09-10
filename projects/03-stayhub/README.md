# 🛎️ StayHub — hotel & room booking engine

> Flagship **#3** of the [django-20-projects](../../README.md) monorepo.
> Django 5.2 LTS · first-party HTML/CSS frontend · hardened security baseline ·
> **33 automated tests, all green.**

A booking engine whose core promise is the hard one: **a room can never be
double-booked.** Availability is computed from live bookings with date-range
overlap semantics, enforced twice — a friendly form check for UX, and a
transactional row-locked check for correctness — and proven by tests.

---

## Feature tour

| Area | What's implemented |
|---|---|
| **Search** | City search, date-range + guest filters, price/star filters, fully-booked hotels automatically hidden for the requested dates |
| **Hotel pages** | Stars, amenities, hero panel; per-room **availability strip** showing the next blocked nights; live total for the exact stay (nights × rate, server-computed) |
| **Booking** | Race-proof `create_booking()` service, capacity validation, 30-night cap, no past check-in, price **snapshot** stored at booking time |
| **Guest area** | "My trips" with statuses (pending → confirmed → completed / cancelled), free online cancellation that instantly releases dates, owner-scoped detail pages |
| **Host area** | Per-host property list with room counts, room manager showing upcoming bookings per room — all owner-scoped (404 for others) |
| **Admin** | Hotel inline room editing, booking date hierarchy, confirm/cancel/complete bulk actions |
| **Demo data** | 4 themed properties (Dhaka, Cox's Bazar, Sylhet, Chattogram), 13 rooms, past + upcoming bookings |

## The double-booking guarantee (the interesting part)

```python
# Booking.create_booking() — core/models.py
with transaction.atomic():
    locked_room = Room.objects.select_for_update().get(pk=room.pk)      # 1. lock
    if not locked_room.is_available(check_in, check_out):              # 2. re-check
        raise ValidationError("…just booked…")
    booking.full_clean()                                               # 3. validate
    booking.total_price = locked_room.price_for(booking.nights)        # 4. snapshot
    booking.save()
```

Interval semantics: a booking occupies `[check_in, check_out)`, so a checkout
on day X and a check-in on day X **do not conflict** (back-to-back stays are
valid) — covered explicitly by `test_overlap_semantics`, which exercises all
six overlap/adjacency cases. Cancelled bookings stop blocking dates; that is
also tested.

## Page map

```
/                          home + search bar + cities + stats
/search/                   results with filters (?city=&check_in=&check_out=&guests=)
/hotels/<slug>/            hotel page, room list, availability strips, book buttons
/rooms/<id>/book/?check_in=&check_out=   booking form (login required)
/bookings/                 my trips
/bookings/<id>/            booking detail (owner-only)
/bookings/<id>/cancel/     POST cancel → dates released
/manage/                   host area
/manage/<slug>/rooms/      rooms + upcoming bookings (owner-only)
/profile/                  account
/admin/                    Django admin
```

## Data model

```
User ──< Hotel ──< Room ──< Booking >── User
        (owner)            (dates, status, price snapshot, guests)
```

- `total_price` is written once at booking and never recomputed — later rate
  changes cannot rewrite history (tested).
- `Booking.clean()` enforces: check-out > check-in, ≤ 30 nights, no past
  check-in, guests ≤ room capacity.
- Composite index on `(room, check_in, check_out)` keeps overlap queries fast.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo            # 4 hotels, 13 rooms, demo bookings
python manage.py runserver
```

**Demo accounts**

| Username | Password | Role |
|---|---|---|
| `host` | `DemoPass123!` | owns all 4 demo properties |
| `alice` | `DemoPass123!` | guest with an upcoming booking |
| `bob` | `DemoPass123!` | guest with past trips |
| `admin` | `DemoPass123!` | superuser |

## Tests — 33 total

- `core/tests_security.py` — 12 canonical security tests
- `core/tests.py` — 21 domain tests: all six overlap/adjacency cases,
  cancellation releasing dates, price snapshotting, validation limits (past,
  zero-night, >30 nights, over-capacity), search hiding booked hotels,
  HTTP-level booking flows, ownership scoping (stranger gets 404 on
  booking/manage pages), stale-page conflict notices, seeder integrity

## Security notes

Beyond the [shared baseline](../../docs/SECURITY.md):

- Cancellation and booking creation are POST-only with CSRF tokens; ownership
  is enforced with `get_object_or_404(Booking, pk=…, guest=request.user)`.
- The host area is scoped by `owner=request.user` — listing another host's
  rooms 404s, not "permission denied" (no information leak).
- Guests can never set prices, totals or statuses; all three are derived or
  admin-only.
