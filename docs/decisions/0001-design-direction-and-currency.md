# ADR 0001 — Design direction and currency display

- Status: Accepted
- Date: 2026-08-13
- Deciders: Product owner (via design checkpoint), lead engineer

## Context

The project brief required three distinct visual directions for the representative screens
(Dashboard, Transactions, Add-expense, Invoice) before production scaffolding, and required a
decision on currency display (rial, toman, or both with an explicit converter).

## Decision

1. **Direction: «کلاسیک و مورداعتماد» (Classic & Trusted).** Deep pine green (`#14604F`) primary
   on warm paper (`#F5F3EC`) surfaces, restrained gold (`#B08A3E`) accents, ledger-inspired double
   rules, small radii, dark-green institutional sidebar. See `design/direction-classic.html` and
   the token set in `apps/web/src/styles/tokens.css`.
2. **Currency display: rial only.** The UI enters and displays rial. No toman toggle in the MVP
   UI. All persistence is integer rial regardless. (Toman conversion remains documented in
   `docs/accounting-rules.md` as an exact 1 toman = 10 rials operation for future needs.)

## Consequences

- Frontend design tokens, Tailwind theme, chart palette, and component primitives derive from the
  classic token set; light/dark themes use the approved classic dark palette.
- One less stateful UI control (unit toggle) and simpler validation; amounts are labeled «ریال».
- The classic look favors dense-but-readable tables; responsive behavior converts tables to
  stacked cards on small screens (verified in the approved mockup).
- Rejected alternatives: modern (airy) direction — too much whitespace for dense financial grids;
  dense direction — too intimidating for occasional staff; toman/both display — adds conversion
  surface area without user demand at MVP.
