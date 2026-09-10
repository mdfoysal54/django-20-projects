# SECURITY.md — the shared hardening checklist

Every flagship project in this monorepo implements the same, test-verified
security baseline. `core/tests_security.py` in each project asserts the
header, registration and throttling guarantees below.

## 1. Configuration & secrets

| Measure | Where |
|---|---|
| All secrets via environment variables (`python-dotenv`, `.env` ignored) | `config/settings.py` |
| `DJANGO_SECRET_KEY` required when `DEBUG=False` (refuses to boot otherwise) | `config/settings.py` |
| `SECRET_KEY` regenerated randomly whenever missing in development | `config/settings.py` |
| `.env.example` documents every variable; real `.env` never committed | project root |
| `ALLOWED_HOSTS` pinned from env (never `*` silently) | `config/settings.py` |

## 2. Transport & cookie security (deployment)

| Flag | Default | Production (behind HTTPS) |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `False` | `True` via `DJANGO_SECURE_SSL_REDIRECT` |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | follows SSL flag | `True` |
| HSTS (`31536000`s, includeSubDomains, preload) | off | on via `DJANGO_HSTS` |
| `SECURE_PROXY_SSL_HEADER` | off | on when behind a trusted proxy |

Both session and CSRF cookies are `HttpOnly`, `SameSite=Lax`; the CSRF token
is not readable by JavaScript. Sessions expire after 7 days.

## 3. Response headers (applied to every response)

| Header | Value |
|---|---|
| `Content-Security-Policy` | `default-src 'self'`; scripts & styles only from `'self'` **with a fresh per-request nonce** (`{{ csp_nonce }}`); `frame-ancestors 'none'`; `object-src 'none'`; `base-uri 'self'`; `form-action 'self'` (+ `upgrade-insecure-requests` when not in DEBUG) |
| `X-Frame-Options` | `DENY` (clickjacking) |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `same-origin` |
| `Permissions-Policy` | camera/mic/geolocation/payment disabled |

The Django admin gets a compatible CSP (`'unsafe-inline'` allowed only under
`/admin/`, where Django's own inline scripts run) — verified by tests.

## 4. Authentication & access control

- Argon2id (`Argon2PasswordHasher`) is the primary password hash; PBKDF2 kept
  as fallback for old hashes.
- Django's four standard validators incl. a **minimum 8 characters**.
- Brute-force protection: sliding-window throttle on the login endpoint —
  5 failed attempts (IP **and** username keyed) → `429 Too Many Requests`.
  Successful logins reset the counters (`core/middleware.py`).
- Account registration enforces **unique, case-insensitive emails**.
- Every object-scoped view uses `get_object_or_404(Model, pk=…, owner=request.user)`
  so users can never read/write other users' rows (IDOR-safe).
- All data mutations are POST + CSRF-token protected forms; destructive
  actions require confirmation pages; no `GET` side-effects.

## 5. Input validation & data

- All forms use Django's bound validation (never trust the client).
- `DATA_UPLOAD_MAX_MEMORY_SIZE` = 2.5 MB; max 1000 form fields.
- ORM-only data access — no raw SQL anywhere; query params never concatenated.
- File/image uploads: extension + size validated server-side, served only via
  Django (no user-controlled paths).
- Output auto-escaped by Django templates; user HTML is never injected.

## 6. Operations

- `DEBUG=False` in production, dedicated error templates (404/403/429/500).
- Static files served via WhiteNoise (compressed, hashed, immutable caching).
- The canonical test-suite (`core/tests_security.py`) runs in CI and fails
  the build if any guarantee regresses.

## Deployment quick check

```bash
# on the server, in production
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(64))')"
export DJANGO_ALLOWED_HOSTS=yourdomain.com
export DJANGO_SECURE_SSL_REDIRECT=True DJANGO_COOKIE_SECURE=True DJANGO_HSTS=True
python manage.py check --deploy
```

`check --deploy` should come back clean (Whitenoise, cookies, headers, HSTS,
referrer policy all covered above).
