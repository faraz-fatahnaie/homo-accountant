# Repository Guide — «آریا تجارت» accounting app

## Goal and priorities

Build a reliable Persian RTL accounting app. Correct ledger behavior, authorization, exact money
handling, and recoverable data come before convenience or visual polish. Preserve posted history;
correct it with reversals.

Work in four loops: (1) define acceptance criteria and implement one complete vertical slice across
DB, backend, API, UI, permissions, and docs; (2) apply unit, integration, API, component,
user-journey, and real-browser E2E tests; (3) QA every affected layer, including RTL/accessibility
and operations; (4) fix findings, add regression tests, rerun until green, and record evidence.
Read nearby code and docs before editing. Keep changes scoped and never hide failing checks.

## Services and ports (local `docker compose up`)

- `api` — FastAPI, port **8000** (`http://localhost:8000`, docs at `/docs`)
- `web` — Next.js, port **3000**
- `db` — PostgreSQL 16, port **5432**
- `storage` — MinIO (S3-compatible), console port **9001**
- `nginx` (prod) — reverse proxy, TLS termination
- Migration entrypoint: `alembic upgrade head` before API start; seed in dev via Make target.

## Structure

- `apps/api/app/domains/`: backend domain modules and business rules
- `apps/api/app/api/`: thin HTTP routes
- `apps/api/tests/`: backend unit/integration tests
- `apps/web/src/features/`: frontend feature modules
- `apps/web/src/components/`: reusable UI primitives
- `packages/api-client/`: typed API contract/client
- `tests/e2e/`: Playwright user journeys
- `infra/`: proxy, backup, and deployment assets
- `.github/workflows/`: CI, E2E, security, and container workflows
- `docs/`: architecture, accounting rules, operations, ADRs (`docs/decisions/`)

Keep accounting logic out of routes and UI. Domains may communicate through explicit services;
avoid circular imports and duplicated totals.

## Domain invariants

- Store ledger money as integer Iranian rials; never use float.
- Store instants in UTC and display `Asia/Tehran`; UI dates use «تقویم شمسی» (Solar Hijri).
- Every posted journal entry must balance in one database transaction.
- Posted entries are immutable. Void/correct them through reversal entries.
- Reports and dashboard totals derive from posted ledger lines.
- Enforce permissions and company scope server-side.
- The visual query builder compiles only allowlisted, parameterized, read-only queries; never
  accept raw SQL.

## UI rules

Persian and RTL are defaults. Isolate codes and technical identifiers with LTR direction. Use
design tokens, one icon set (no emoji), accessible semantic controls, visible focus, and WCAG AA
contrast. Support intentional light/dark themes and responsive layouts. Do not use color as the
only status signal. Provide loading, empty, validation, error, and success states. Verify desktop
and mobile layouts; generated PDFs must embed a Persian-capable font (Vazirmatn).

## Build and test

Use repository scripts/Make targets as the source of truth; keep these working or update this file:

```bash
docker compose up --build
make format
make lint
make typecheck
make test
make test-e2e
make build
```

Use available test/QA skills when present; otherwise use repository-native commands without
inventing tools. Add tests with every behavior change. Accounting changes require invariant and
expected debit/credit tests. API changes require authorization and integration tests. UI changes
require component coverage plus a browser check at mobile and desktop widths. Before handoff run
formatting, linting, type checks, relevant tests, migration checks, and production builds; report
exact results and any unrun check.

**Windows quick start (PowerShell):**
```powershell
cd apps\api
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # then `make` targets work via `python -m ...`
python -m pip install -r requirements.txt -r requirements-dev.txt
cd ..\..; docker compose up -d db minio; make test-db-create
make lint; make typecheck; make test-api; make test-web; make build
# PowerShell 5.1 has no `&&` — chain with `;` or run one target per line.
```

Use real PostgreSQL and the real API for core E2E journeys. Every bug fix needs a regression test.
Initial coverage floors: 90% accounting services, 80% backend overall, 75% frontend logic;
meaningful assertions matter more than percentages. CI workflows run for pull requests and `main`,
use least privilege and timeouts, retain reports/failure traces, and never commit generated results
automatically.

Keep README workflow badges and its **Quality and test status** section factual. Record the last
fully verified commit, time, environment, commands, and results; never invent passing checks or
coverage. Commit workflow files to `main` only when the required checks pass; never force-push or
bypass protection.

## Design checkpoint (status)

Three visual directions were produced under `design/` and presented for approval before production
scaffolding began. Approved direction → design tokens in `apps/web` + documented ADR. Do not
silently pick a direction; the choice is recorded in `docs/decisions/`.

## Safety and delivery

Validate input at boundaries, use migrations for schema changes, and keep secrets out of Git. Do
not weaken tests, edit posted financial data directly, expose attachments, execute arbitrary SQL,
or deploy externally without explicit authorization. Keep `README.md`, `.env.example`,
OpenAPI/client types, accounting rules, and deployment docs synchronized with code.

Note: `skills/`, `uploads/`, `.claude/`, `.fonts/` are agent tooling/workspace artifacts, not part
of the product repository (gitignored).
