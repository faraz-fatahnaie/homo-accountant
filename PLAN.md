# Plan — «آریا تجارت» Persian-First Accounting MVP

## Mission

Design, implement, test, document, containerize, and prepare for deployment a Persian-first
(Solar Hijri calendar, RTL, rial) accrual accounting web application for one small Iranian
company (~3–4 users): expenses, supplier bills, customer invoices, payments, projects, budgets,
funding, and a true double-entry ledger. Ledger is the source of truth; reports derive from posted
entries; posted history is immutable and corrected via reversals. Operational product, not audit
product — but with a tamper-evident activity trail.

## Fixed product decisions (from brief — not re-negotiable)

- One tenant/company; ~3–4 users; responsive web only (no native mobile).
- Persian-first UI, full RTL; Solar Hijri UI dates (labeled «تقویم شمسی», never “Jalali” in UI);
  instants stored UTC, rendered Asia/Tehran.
- Integer rial storage; explicit exact rial⇄toman conversion (1 toman = 10 rials).
- Accrual, mandatory balanced double-entry; no tax/VAT; no OCR; bank-statement import deferred.
- Roles: Owner/Admin, Accountant, Staff, Viewer — server-enforced (hiding buttons ≠ authorization).
- Deploy: Linux VPS, Docker Compose, reverse proxy, HTTPS-ready, backups, health checks, runbook.
- Stack: FastAPI + Pydantic + SQLAlchemy 2.x + Alembic + PostgreSQL | Next.js + TS + Tailwind +
  shadcn/ui-equivalent + TanStack Query/Table | pytest | Vitest + Testing Library | Playwright |
  Ruff + mypy | ESLint + strict TS | MinIO (S3-compatible) | Redis+worker only when a real MVP
  workflow needs it | OpenAPI-generated typed client (packages/api-client).

## Milestones (vertical slices; each ends runnable + documented)

| # | Slice | Key acceptance criteria (subset) |
|---|---|---|
| 0 | Design checkpoint | 3 approved visual directions (Dashboard, Transactions, Add-expense, Invoice); design tokens; then scaffold |
| 1 | Foundation: repo, local env, identity, RBAC, design system, RTL shell, themes | authn/authz enforced on API; roles seeded; migrations run from clean DB; light/dark themes; RTL |
| 2 | CoA, journal, posting service, periods, seed data, invariants | unbalanced entries rejected; posted lines immutable; period close blocks posting; reopening recorded; conversion exact |
| 3 | Contacts, projects, expenses, attachments, optional approval | full expense lifecycle Draft→Posted→Paid (+approval threshold off by default); file restrictions + authz; allocations |
| 4 | Customer invoices, receivables, incoming payments, PDF | invoice lifecycle incl. partial payment entries; PDF with embedded Persian font; aging/overdue views |
| 5 | Supplier bills, payables, outgoing payments | bill lifecycle; partial payments; payables aging |
| 6 | Funding events + ledger mappings | investment/loan/grant/revenue post correctly; loans ≠ revenue; explicit account mappings |
| 7 | Excel-like tables, saved views, exports, safe query builder | server-side filter/sort/paginate; CSV/XLSX/PDF honor filters + neutralize formulas; query builder AST allowlist, no raw SQL |
| 8 | Dashboard, reports, drill-downs, reconciliation | all figures reconcile to posted ledger; TB, GL/journal, BS, P&L, cash flow (documented method), aging, budget vs actual, funding summary |
| 9 | Hardening: security, a11y, responsive QA, backups, prod assets | headers/CORS/rate-limit/CSRF; uploads hardened; backup+restore tested locally; compose.prod + nginx + runbook; CI/CD workflows |

## Risks & mitigations

- **Money correctness** — integers only, decimal-free arithmetic, invariant + property tests, exact
  conversion tests. (High)
- **Date correctness** — Solar Hijri round-trip across Tehran midnight; store UTC instant + fiscal
  date; property tests around day boundaries. (High)
- **Posting integrity** — single-DB-transaction balanced posting, idempotency keys, constraint
  backstops, reversal-only corrections. (High)
- **Scope creep** — OCR/tax/bank-reconcile explicitly deferred; approvals off by default; Redis only
  with a consumer. (Medium)
- **Environment limits** — no Docker/psql in this sandbox (verified): container/E2E-against-compose
  checks authored + documented, executed by user via provided commands; local non-Docker equivalents
  (SQLite-free: real Postgres via local install if possible, else documented CI-only path). (Medium)
- **RTL/a11y** — container-query responsive checks, keyboard/focus audits, WCAG 2.2 AA checklists,
  Playwright a11y + visual tests. (Medium)

## QA approach (per slice and full-system)

Loop 1: define acceptance criteria + risks + accounting effects + tests, then implement the whole
vertical slice. Loop 2: full test pyramid (unit/property → DB/service integration → API/authz →
frontend unit/component → user-journey → real-browser Playwright → export/security/migration/
container-smoke/perf where applicable). Loop 3: cross-layer QA incl. RTL/a11y, theme states,
ledger reconciliation of every UI total. Loop 4: classify findings, fix, regression-test each,
rerun, record evidence. Never silence failing tests.

**Coverage gates:** ≥90% accounting domain services · ≥80% backend · ≥75% frontend logic —
meaningful positive+negative assertions on invariants and permission boundaries.

## Skills to engage (installed under `skills/`)

ui-designer (design phase), frontend-developer + ui-ux-tester (UI + QA), api-designer +
api-testing (contracts/tests), backend-developer (services), data-analyst (reports/BI patterns),
test-automator (test strategy), code-reviewer (per-slice review), docker-expert + devops-engineer +
deployment-engineer (containers/CI/deployment), project-manager (slice tracking), product-manager
(priorities).

## Status

- [x] Skills installed (15) — see `skills/README.md`
- [x] Foundation docs (this plan, AGENTS.md, README, .gitignore)
- [x] **Design checkpoint** — three directions produced in `design/` (`direction-classic.html`,
      `direction-modern.html`, `direction-dense.html`), QA'd via headless-Chromium screenshots +
      interaction smoke test, presented for approval
- [ ] Design approval → tokens + ADR → Slices 1–9
