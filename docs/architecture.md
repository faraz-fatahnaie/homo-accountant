# معماری — Architecture

Status: evolving with slices (slice 1 implemented). See ADRs under `docs/decisions/`.

## Shape: modular monolith

A single deployable unit with strict domain boundaries — not a distributed system, so the MVP
keeps transactional integrity, simple ops, and fast iteration. Boundaries are enforced at the
module level; domains communicate through explicit services, never via shared mutable state.

```text
apps/api/app/
├── core/        config, db, security, logging, rate limiting, errors
├── domains/     identity (implemented) · ledger, contacts, projects, expenses,
│                receivables, payables, funding, reports, queries, files, activity (upcoming)
└── api/         thin HTTP routes + deps (no business logic in routes)
```

## Key flows (slice 1)

1. **Login** — `POST /api/v1/auth/login` (rate-limited per IP) → PBKDF2-SHA256 verify →
   short-lived JWT access token (30 min) + opaque refresh token (7 days, stored hashed).
2. **Refresh** — rotation: old token revoked, new pair issued; reuse of a revoked token revokes
   the family (theft detection).
3. **Authorization** — every protected endpoint resolves the token → live user → role check
   (`require_roles`); object-level checks are added per resource as domains land.
4. **Health** — `/health/live` (process) and `/health/ready` (DB reachability) for orchestration.

## Cross-cutting

- **Money:** integer rial throughout (no floats) — enforced from slice 2 by the ledger types.
- **Time:** instants stored UTC (`timestamptz`); UI renders `Asia/Tehran`; Solar Hijri UI dates.
- **Errors:** uniform envelope `{"error": {"code", "message", "details"}}` (see `app/api/errors.py`).
- **Observability:** structured JSON logs (prod), `X-Request-ID` correlation, security headers,
  CORS allowlist, login rate limiting.
- **Security:** PBKDF2-SHA256 hashing, JWT + rotated refresh, secrets via env only, no secrets in
  git (`.env.example` only), safe bootstrap (`bootstrap_admin`), demo seed refused in production.

## Frontend

Next.js 15 App Router, TypeScript strict (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`),
Tailwind mapped to design tokens (`apps/web/src/styles/tokens.css`, ADR-0001 classic direction),
RTL + Persian by default, light/dark via `[data-theme]` with no-FOUC pre-hydration script,
self-hosted Vazirmatn. Client calls the API through `src/lib/api.ts`; from slice 2 this is
replaced by the generated `packages/api-client` types (OpenAPI) to prevent contract drift.

## Deployment topology (production)

`nginx (TLS) → web:3000 + api:8000` · `PostgreSQL 16` · persistent Docker volume (attachments).
Single VPS,
Docker Compose (`compose.prod.yaml`). Details in `docs/deployment.md` and `docs/operations.md`.
