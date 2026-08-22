# Homo Accountant — سامانه حسابداری فارسی (Persian Accounting)

Production-ready MVP of a Persian-first (Solar Hijri, RTL, rial) accrual accounting web app for a
small Iranian company (~3–4 users): expenses, supplier bills, customer invoices, payments,
projects, budgets, funding, and a double-entry ledger that is the source of truth.

Production: [https://mohotec.ir/](https://mohotec.ir/)

## کیفیت و وضعیت تست — Quality and test status

**Workflow badges** (live after the repository is published to GitHub — replace `faraz-fatahnaie/homo-accountant` in the
URLs; a badge is always the live source for the branch, the prose below is a dated snapshot):

[![CI](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/ci.yml?label=CI)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/ci.yml)
[![E2E](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/e2e.yml?label=E2E)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/e2e.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/security.yml?label=Security)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/security.yml)
[![Docker](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/docker.yml?label=Docker)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/docker.yml)

> **Last verified:** commit `53c78db` · 2026-08-17 · GitHub Actions on Ubuntu with Python,
> Node 20, PostgreSQL, Docker, Trivy, and Chromium (Playwright). **CI, E2E, Security, and Docker
> workflows pass.** The production HTTP profile was also smoke-tested on Ubuntu 24.04; database
> backup/restore and persistent receipt storage were rehearsed successfully.

### Test matrix

| Layer | Tool | Result | Notes |
|---|---|---|---|
| Backend unit/API/integration | pytest | ✅ 239 passed | + security headers, prod surface, upload magic-byte, no-cookie/CSRF tests |
| Backend coverage | pytest-cov | ✅ 93% (floor 80%) | ledger 99% · expenses 92% · reports 96% |
| Lint / format | Ruff | ✅ | `ruff check` + `ruff format --check` |
| Types | mypy (strict) | ✅ | 18 source files clean |
| Migrations | Alembic | ✅ | upgrade head; downgrade→upgrade exercised in tests |
| Frontend unit/component | Vitest + Testing Library | ✅ 52 passed | + reports hub/reconciliation, trial balance, dashboard KPIs |
| Frontend lint | ESLint | ✅ | 0 errors/warnings |
| Frontend types | tsc strict | ✅ | `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` |
| Frontend build | next build | ✅ | standalone output |
| Browser journeys | Playwright | ✅ 78 passed | desktop + mobile; **reports journeys + axe WCAG 2.2 A/AA scans**; auth-session-resilience fix verified |
| Accessibility lint | axe | ✅ 0 serious/critical | automated WCAG 2.2 A/AA scans on key surfaces (login, dashboard, transactions, reports, guide) |
| Docker builds/smoke | compose.prod + Trivy | ✅ | production images build; API/web health smoke and fixable HIGH/CRITICAL image gate pass in `docker.yml` |
| Security scans | npm audit | ✅ 0 vulnerabilities | Next 15.3.4 → 15.5.23 (CVE-2025-66478); postcss/sharp overrides; pip-audit/trufflehog/CodeQL run in `security.yml` |
| PDF/export tests | — | ⏳ slice 4/7 | with their features |
| Backup/restore smoke | infra/backup | ✅ | production snapshot restored into a scratch database; all 22 public tables verified |

### Commands

```bash
# quick checks
make lint && make typecheck && make test-api && make test-web && make build

# full local QA
make quality          # format + lint + typecheck + backend+frontend tests + build

# end-to-end against the real stack
make dev              # docker compose up (PostgreSQL + MinIO + API + web)
make e2e              # Playwright role journeys (desktop + mobile)

# packaged local runner (docker mode, or --bare with local PostgreSQL)
./scripts/run-local.sh        # docker compose dev stack, migrates + seeds, prints URLs
./scripts/run-local.sh --bare # no docker: local Postgres + uvicorn + next dev

# deployment (Linux VPS)
sudo ./scripts/deploy.sh --domain your.domain --email you@example.com
sudo ./scripts/deploy.sh --update

# backend alone (expects local PostgreSQL: see PLAN.md/AGENTS.md)
make migrate && make seed && make test
```

### Coverage policy

Floors: **90%** accounting domain services · **80%** backend overall · **75%** frontend logic.
Coverage is a floor, not a goal — accounting invariants and permission boundaries require explicit
positive **and** negative tests. Reports: `artifacts/quality-summary.json` (machine-readable) and
`docs/quality-report.md` (human-readable); CI uploads coverage + Playwright traces on failure.

### Known limitations / deferred

- OCR, tax/VAT, bank-statement import — explicitly out of scope (fixed product decisions).
- Email reminders & live online-payment integration — deferred (documented in the invoice/funding
  slices); Stripe exists only as disabled example infrastructure for legally supported regions.
- OCR and automated tax handling remain intentionally deferred; current financial reports and
  dashboard totals derive from posted ledger lines.

## Quick start (dev)

```bash
cp .env.example .env            # adjust as needed
make dev                        # full stack at http://localhost:3000
```

Demo users (dev only, seeded automatically): `owner@example.com / owner-homo-1405`,
`accountant@example.com / acct-homo-1405`, `staff@example.com / staff-homo-1405`,
`viewer@example.com / viewer-homo-1405`.

## Repository map

- [`PLAN.md`](PLAN.md) — milestones, risks, acceptance criteria, QA gates
- [`AGENTS.md`](AGENTS.md) — repository guide (domains, invariants, commands)
- [`design/`](design/) — approved classic direction + QA screenshots
- [`docs/`](docs/) — architecture, accounting rules, deployment, operations, ADRs
- [`apps/api`](apps/api) — FastAPI backend · [`apps/web`](apps/web) — Next.js frontend
- [`packages/api-client`](packages/api-client) — typed client (slice 2)
- [`tests/e2e`](tests/e2e) — Playwright journeys · [`infra/`](infra) — proxy/backup/scripts

## Deployment

Linux VPS + Docker Compose + nginx (TLS) — see [`docs/deployment.md`](docs/deployment.md) runbook
and [`docs/operations.md`](docs/operations.md). Nothing is published or deployed without explicit
owner credentials and authorization.
