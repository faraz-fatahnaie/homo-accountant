# گزارش کیفیت — Quality Report

Snapshot from the most recent complete local verification run.
Machine-readable copy: `artifacts/quality-summary.json`.

## Last verified

- **Commit:** `3df4d92` (slice 8 — dashboard KPIs, financial reports, drill-downs, reconciliation)
- **UTC:** 2026-08-13T21:45:00Z
- **Environment:** Debian 13 sandbox · Python 3.13.14 · Node 20.20.2 · PostgreSQL 17.10
  (local) · Chromium 151 (Playwright)

## Results

| Check | Result | Detail |
|---|---|---|
| Backend Ruff | ✅ pass | `ruff check` + `ruff format --check` clean |
| Backend mypy | ✅ pass | strict, 18 source files, 0 issues |
| Backend pytest | ✅ 231/231 | real PostgreSQL (`arya_test`), migrations applied |
| Backend coverage | ✅ 93% | floor 80%; ledger 99%, expenses 92%; **reports 96%** |
| Migrations | ✅ pass | upgrade on dev+test; downgrade→upgrade exercised in tests |
| Frontend ESLint | ✅ pass | 0 errors / 0 warnings |
| Frontend typecheck | ✅ pass | `tsc --noEmit`, strict options on |
| Frontend Vitest | ✅ 52/52 | + reports hub/reconciliation, trial balance, dashboard KPIs |
| Frontend build | ✅ pass | `next build` (standalone) |
| Playwright E2E | ✅ 54/54 | real stack; report journeys to be added in the slice-9 E2E pass |
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
with their feature slices, Next.js 15.3.4 upgrade (CVE-2025-66478) scheduled for slice 9.
