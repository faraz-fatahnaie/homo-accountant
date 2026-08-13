# گزارش کیفیت — Quality Report

Snapshot from the most recent complete local verification run.
Machine-readable copy: `artifacts/quality-summary.json`.

## Last verified

- **Commit:** `76d5bd2` (`feat(slice1): frontend shell, infra, CI/CD, docs`)
- **UTC:** 2026-08-13T08:35:00Z
- **Environment:** Debian 13 sandbox · Python 3.13.14 · Node 20.20.2 · PostgreSQL 17.10
  (local) · Chromium 151 (Playwright)

## Results

| Check | Result | Detail |
|---|---|---|
| Backend Ruff | ✅ pass | `ruff check` + `ruff format --check` clean |
| Backend mypy | ✅ pass | strict, 18 source files, 0 issues |
| Backend pytest | ✅ 108/108 | real PostgreSQL (`arya_test`), migrations applied |
| Backend coverage | ✅ 93% | floor 80%; ledger domain service 99% (floor 90%) |
| Migrations | ✅ pass | upgrade on dev+test; downgrade→upgrade exercised in tests |
| Frontend ESLint | ✅ pass | 0 errors / 0 warnings |
| Frontend typecheck | ✅ pass | `tsc --noEmit`, strict options on |
| Frontend Vitest | ✅ 26/26 | API client, login, Solar Hijri formatter, transactions, user guide |
| Frontend build | ✅ pass | `next build` (standalone) |
| Playwright E2E | ✅ 30/30 | real stack; 4 roles × desktop+mobile; RBAC direct-API; themes; ledger journey; per-role user guide |
| Docker builds | ⛔ not run | no docker in sandbox — authored; runs in `docker.yml` |
| Security scans | ⛔ not run | wired in `security.yml` (pip-audit, npm audit, trufflehog, CodeQL, trivy) |

## Commands to reproduce

```bash
# backend
cd apps/api && pip install -r requirements.txt -r requirements-dev.txt
ruff check app/ tests/ migrations/env.py && ruff format --check app/ tests/
mypy app/
ARYA_DATABASE_URL=postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_test \
  python -m pytest tests/ --cov=app

# frontend
cd apps/web && npm ci && npx eslint . && npx tsc --noEmit && npx vitest run && npm run build

# e2e (requires the compose stack: make dev)
cd tests/e2e && npm ci && npx playwright test
```

## Known limitations & deferred

See `artifacts/quality-summary.json` → `known_limitations`. Highlights: Docker execution
unavailable in this sandbox (documented, reproducible via Make/CI), axe/PDF/export tests land
with their feature slices, dashboard figures become ledger-derived in slice 8.
