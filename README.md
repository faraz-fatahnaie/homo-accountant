# آریا تجارت — حسابداری فارسی (Arya Tejarat · Persian Accounting)

Production-ready MVP of a Persian-first (Solar Hijri, RTL, rial) accrual accounting web app for a
small Iranian company (~3–4 users): expenses, supplier bills, customer invoices, payments,
projects, budgets, funding, and a double-entry ledger that is the source of truth.

> **Status: design phase.** Three visual directions are presented in [`design/`](design/) and are
> awaiting approval before production scaffolding (per the project brief's mandatory checkpoint).

## Contents

- [`PLAN.md`](PLAN.md) — milestones, risks, acceptance criteria, QA gates
- [`design/`](design/) — three UI directions (Dashboard, Transactions, Add-expense, Invoice; RTL,
  light/dark, desktop/mobile)
- `AGENTS.md` — repository guide for agentic workflows
- `docs/` — architecture, accounting rules, deployment, operations, ADRs (filled in as slices land)

## Stack

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · Next.js/TypeScript · Tailwind · TanStack Query ·
pytest · Vitest · Playwright · Docker Compose · MinIO. Full details in `PLAN.md` and
`docs/architecture.md` (once implemented).

## Roadmap

Slices 1–9 per `PLAN.md`. This README will gain live workflow badges, a factual test matrix,
coverage policy, and a dated **Quality and test status** snapshot after the first genuinely
verified run — never fabricated.
