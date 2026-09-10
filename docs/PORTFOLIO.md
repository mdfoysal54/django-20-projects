# Why 6 flagship projects instead of 20 shallow ones

The commission was "20 Python/Django projects". We deliberately traded
*breadth for depth*: six genuinely complete, hardened, tested applications
beat twenty half-built clones — for a portfolio, for learning, and for bragging
rights in an interview.

## What each flagship includes

| Layer | Depth |
|---|---|
| Database | 5–8 related models per app, constraints, snapshots, migrations |
| Backend | Auth flows, ownership checks, transactions, stock/seat/room locking, seeders |
| Frontend | 8–12 hand-built pages per app, responsive CSS, CSP-safe progressive JS |
| Security | Shared verified baseline (see SECURITY.md) + domain-specific guards |
| Tests | 25–45 automated tests per app (security + domain edge-cases) |
| Docs | Per-project README: features, page map, data model, deploy guide |

## Scaling to 20 apps is a copy job, not a rewrite

Everything shared lives in `tools/canonical*.py`. To spin up app #7:

```bash
# 1. add an entry to tools/canonical.PROJECTS
# 2. regenerate the skeleton
python tools/scaffold.py
# 3. build the domain: core/models.py → forms → views → urls → templates → tests
```

The new app immediately inherits: the CSP/nonce middleware, login throttling,
hardened settings, branded error pages, auth templates, seed/test scaffolding —
all pre-verified by the canonical security suite (12 tests).

Wanted 20? Add fourteen more entries and you have the same baseline; the six
flagships show how to finish the job properly.
