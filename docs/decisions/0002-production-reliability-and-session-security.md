# ADR 0002 — Production bootstrap, browser sessions, reversals, and monitoring

Status: accepted (2026-08-22)

## Context

Production could start without required system accounts, browser tokens were exposed to
JavaScript storage, and repeated reversal requests could create multiple corrections. Failures
also lacked an optional centralized diagnostic channel.

## Decision

- Production startup idempotently creates only missing system accounts and funding mappings; it
  never overwrites company data. Startup fails if this invariant cannot be established.
- Browser sessions use Secure (in production), HttpOnly, SameSite=Lax cookies. Refresh tokens are
  rotated; reuse revokes the token family. Bearer access remains supported for non-browser clients.
- A posted journal entry may have at most one reversal. The original is locked while the reversal
  is checked and created, and both operations are company-scoped. Migration `0008` repairs any
  legacy duplicate without deleting history: it posts a balancing correction for each extra
  reversal, relinks that pair, and then adds a database uniqueness constraint.
- Sentry is optional and disabled when no DSN is configured. Personally identifiable request data
  is not sent, and tracing defaults to zero.

## Consequences

Production boot is safer and deterministic, browser token theft through XSS is reduced, reversal
history stays unambiguous, and operators can opt into correlated error diagnostics. Same-origin
deployment remains required for cookie authentication.
