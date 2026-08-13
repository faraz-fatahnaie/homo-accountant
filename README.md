# Homo Accountant — سامانه حسابداری فارسی (Persian Accounting)

Production-ready MVP of a Persian-first (Solar Hijri, RTL, rial) accrual accounting web app for a
small Iranian company (~3–4 users): expenses, supplier bills, customer invoices, payments,
projects, budgets, funding, and a double-entry ledger that is the source of truth.

## کیفیت و وضعیت تست — Quality and test status

**Workflow badges** (live after the repository is published to GitHub — replace `faraz-fatahnaie/homo-accountant` in the
URLs; a badge is always the live source for the branch, the prose below is a dated snapshot):

[![CI](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/ci.yml?label=CI)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/ci.yml)
[![E2E](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/e2e.yml?label=E2E)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/e2e.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/security.yml?label=Security)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/security.yml)
[![Docker](https://img.shields.io/github/actions/workflow/status/faraz-fatahnaie/homo-accountant/docker.yml?label=Docker)](https://github.com/faraz-fatahnaie/homo-accountant/actions/workflows/docker.yml)

> **Last verified:** commit `76d5bd2` · 2026-08-13T08:35:00Z · Debian 13 sandbox, Python 3.13,
> Node 20, PostgreSQL 17 (local), Chromium (Playwright). **All locally runnable checks pass** —
> full matrix below; `docs/quality-report.md` + `artifacts/quality-summary.json` hold the
> machine-readable snapshot. Docker builds and security scans are wired in CI and were **not**
> runnable inside the sandbox (no Docker) — do not treat them as passed.

### Test matrix

| Layer | Tool | Result | Notes |
|---|---|---|---|
| Backend unit/API/integration | pytest | ✅ 108 passed | real PostgreSQL; auth flows, RBAC, rotation, rate limit, ledger invariants |
| Backend coverage | pytest-cov | ✅ 93% (floor 80%) | ledger domain service 99% (floor 90%) |
| Lint / format | Ruff | ✅ | `ruff check` + `ruff format --check` |
| Types | mypy (strict) | ✅ | 18 source files clean |
| Migrations | Alembic | ✅ | upgrade head; downgrade→upgrade exercised in tests |
| Frontend unit/component | Vitest + Testing Library | ✅ 26 passed | API client, login, Solar Hijri formatter, transactions, user guide |
| Frontend lint | ESLint | ✅ | 0 errors/warnings |
| Frontend types | tsc strict | ✅ | `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` |
| Frontend build | next build | ✅ | standalone output |
| Browser journeys | Playwright | ✅ 30 passed | real stack; 4 roles × desktop/mobile; RBAC direct-API; themes; ledger journey; user guide per role |
| Accessibility lint | axe | ⏳ slice 3+ | wired with UI slices; manual WCAG checks in design mockups |
| Docker builds/smoke | compose.prod + trivy | ⏳ CI only | authored; runs in `docker.yml` |
| Security scans | pip-audit/npm audit/trufflehog/CodeQL | ⏳ CI only | wired in `security.yml` |
| PDF/export tests | — | ⏳ slice 4/7 | with their features |
| Backup/restore smoke | infra/backup | ⏳ ops | scripts authored; rehearsal documented in `docs/operations.md` |

### Commands

```bash
# quick checks
make lint && make typecheck && make test-api && make test-web && make build

# full local QA
make quality          # format + lint + typecheck + backend+frontend tests + build

# end-to-end against the real stack
make dev              # docker compose up (PostgreSQL + MinIO + API + web)
make e2e              # Playwright role journeys (desktop + mobile)

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
- Dashboard figures are design samples until slice 8 derives them from posted ledger entries.
- `packages/api-client` generated from OpenAPI lands in slice 2 (drift guard in CI).

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
