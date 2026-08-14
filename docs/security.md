# امنیت — Security hardening (slice 9)

## Threat model

A small, self-hosted accounting web app (FastAPI + Next.js) for ~3–4 users. The ledger is the
source of truth; integrity and confidentiality of posted financial data matter most. This page
documents the controls in place, how they were verified, and the residual risks.

## Transport & TLS

- **nginx terminates TLS** (TLS 1.2/1.3 only), redirects HTTP → HTTPS, hides `server_tokens`,
  limits body size to 20 MB (attachments), and adds security headers on every response
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`,
  `Strict-Transport-Security`). Validated with a real `nginx -t` (slice 9).
- **Defense-in-depth login rate limit** at nginx on `/api/v1/auth/login` (`limit_req`,
  20 req/min + burst) in addition to the API's own limiter.

## API security

- **Auth:** PBKDF2-HMAC-SHA256 (600k iterations, per-user salt), short-lived HS256 access JWTs,
  opaque refresh tokens stored hashed and rotated (slice 1). Bearer tokens live in
  localStorage and are sent with `credentials: "omit"` — **no cookies, so CSRF does not apply**
  (asserted by a test: no `Set-Cookie` anywhere).
- **RBAC** is server-enforced on every endpoint (`require_roles`), not hidden buttons.
- **Rate limiting** on `/auth/login` (sliding window, 10/min default; prod default; dev/E2E raises
  it — see CI notes below).
- **Headers/CSP:** all API responses carry nosniff, DENY frame options, Referrer-Policy,
  Permissions-Policy, CSP (`frame-ancestors 'none'`), and `X-Request-ID` correlation, including
  error responses. In production `/docs` and `/openapi.json` are disabled.
- **Uploads:** only JPG/PNG/PDF, ≤ 5 MB, and — new in slice 9 — **magic-byte signature checks**
  (`sniff_content_type`) so a spoofed content-type with HTML/JS payload is rejected
  (`upload_content_mismatch`). Downloads are served with `Content-Disposition: attachment` +
  nosniff (no inline rendering → no stored-XSS path).
- **Ledger integrity** (slices 2–8): balanced double-entry enforced in the posting service and by
  DB check constraints; posted lines immutable; reversals only; every report reconciles to the
  posted ledger and surfaces a `reconciled` flag.

## Web security

- **Dependency CVEs fixed (slice 9):** Next.js `15.3.4 → 15.5.23` (CVE-2025-66478 React2Shell and
  the July 2026 advisories; earlier 15.x minors are not patched), nested `postcss` forced to
  `^8.5.23` and `sharp` to `^0.35.0` via `package.json` overrides. **`npm audit`: 0
  vulnerabilities** (prod and full trees).
- **CSP:** delivered per-request by `src/middleware.ts` (not a static header — a static
  `default-src 'self'` was verified to **break** Next.js RSC inline bootstrap scripts in a real
  browser). `script-src 'self' 'unsafe-inline'` is required because App Router pages are
  statically prerendered (per-request nonces can't be baked into cached HTML — verified
  empirically); every other directive stays strict (`frame-ancestors 'none'`, `base-uri 'self'`,
  `form-action 'self'`, restricted `connect-src`, `font-src`, `img-src`).
- **Auth-session resilience (fixed in slice 9):** a full-page navigation used to abort the
  in-flight `me()` check, which the old code treated as session death → `clearTokens()` →
  logged-out flash (reproduced 10/30 in a tight loop; fixed to 0/40). Now only a definitive
  **401** clears the session; transient failures (aborted fetch, network blip, 5xx) retry
  (2× backoff) and never wipe tokens.
- **A11y keyboard access:** scrollable regions (report tables, guide table, sidebar nav) are now
  focusable with `tabIndex` + `role="region"`/`aria-label` (axe `scrollable-region-focusable`).

## Secrets & config

- Secrets live only in `.env` on the VPS; `.env` is never committed; `infra/nginx/ssl/` is
  gitignored (certs are mounted at deploy).
- Production disables the docs surface; `HOMO_ENVIRONMENT` gates dev-only seeding and CORS.
- CORS allowlist is explicit (`HOMO_CORS_ORIGINS`).

## Verification (all run in this sandbox, real Postgres + real Chromium)

- Backend: 239 pytest tests incl. **security-header, prod-surface, upload-sniffing and
  no-cookie/CSRF tests**; ruff + mypy clean.
- Frontend: tsc strict, ESLint clean, 52 unit/component tests; `npm audit` 0 vulnerabilities.
- E2E: **78 Playwright tests** (desktop + mobile) against the real stack, including new
  report journeys and **axe WCAG 2.2 A/AA scans** on login, dashboard, transactions, reports
  hub, trial balance, cash flow and the guide — 0 serious/critical violations.
- Browser-verified CSP: 0 violations and full rendering (was 10 violations + broken page).
- `nginx -t` clean; compose YAML validated; backup/restore rehearsed on real Postgres.

## Residual risks / notes

- `script-src 'unsafe-inline'` weakens script-level CSP (inherent to static App Router pages);
  frame-ancestors, base-uri, form-action and connect-src still constrain injection impact.
  Revisit when the app moves fully to dynamic rendering or Next.js nonce support for static HTML.
- The login rate limiter is in-memory (single-process); scale-out deployments should move it to
  Redis (interface is ready in `app/core/ratelimit.py`).
- E2E/CI raise `HOMO_LOGIN_RATE_LIMIT_PER_MINUTE` (1000) so parallel workers don't 429; prod
  stays at the default 10/min.
