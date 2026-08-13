# طراحی محصول — سه جهت بصری (Design Directions)

Persian-first, RTL, light+dark, desktop+mobile design exploration for the four representative
screens required by the brief: **Dashboard, Transactions/expenses table, Add-expense form,
Invoice builder/detail**. Realistic Persian accounting content; amounts in rial with exact
toman⇄rial conversion; Solar Hijri dates («تقویم شمسی»); coherent figures (all dashboard numbers
reconcile to the transaction sample set).

## How to view

Open any of the three files in a browser (they are fully self-contained — embedded Vazirmatn font,
inline SVG icons, no external resources):

| File | Direction |
|---|---|
| [`direction-classic.html`](direction-classic.html) | جهت ۱ — کلاسیک و مورداعتماد |
| [`direction-modern.html`](direction-modern.html) | جهت ۲ — نوین و روشن |
| [`direction-dense.html`](direction-dense.html) | جهت ۳ — فشرده و کارآمد |

Each file has a fixed review bar (not part of the product) to switch:
**screen** (داشبورد / تراکنشها / ثبت هزینه / صورتحساب), **device** (دسکتاپ / موبایل),
**theme** (روشن / تیره). Screenshots for QA are in [`shots/`](shots/).

## Directions at a glance

### جهت ۱ — کلاسیک و مورداعتماد (`direction-classic.html`)
Traditional, institutional, ledger-inspired. Deep pine green + warm paper cream + restrained gold.
Double-ruled table headers (ledger-paper feel), dark green sidebar, thin borders, sharp corners,
small radii, dense-but-readable tables, subtle gold active-state accents.
**Psychology:** stability, trust, heritage — the "bank / accounting firm" look.
**Trade-offs:** most conservative and least trendy; smaller radii and flat surfaces can read as
less modern; very safe for accountants used to classic ERP software.

### جهت ۲ — نوین و روشن (`direction-modern.html`)
Modern SaaS, airy and friendly. Indigo/blue primary on soft slate, generous whitespace, rounded
cards with soft shadows, pill badges, larger type, 10–14px radii, lighter weight typography.
**Psychology:** calm, approachable, modern — lowers intimidation for non-accountant staff.
**Trade-offs:** more whitespace means fewer rows visible per screen (weaker for heavy data
browsing); softer aesthetics can feel less "serious" to finance purists; slightly more visual
chrome (shadows/cards).

### جهت ۳ — فشرده و کارآمد (`direction-dense.html`)
Power-user accounting workstation. Steel slate + warm amber focus, high data density (12px base,
compact rows), minimal chrome, strong grid lines, keyboard-hint affordances (`/` for search),
amber active/focus accents, sticky dense headers.
**Psychology:** precision, speed, control — for a professional accountant who lives in the grid.
**Trade-offs:** densest and most efficient, but more intimidating for occasional users; smaller
type requires good AA contrast (verified) and may need scaling on small screens; less "warm".

## Common properties (all three)

- **RTL + Persian** everywhere; technical identifiers (`EX-1405-0231`, account codes) isolated LTR.
- **Light & dark** intentional themes with persistent preference (demo uses localStorage).
- **Single SVG icon set** (no emoji), stroke-based, `currentColor`.
- **Status never color-only**: badges pair icon + label (پرداختشده ✓، معوق ⚠، پیشنویس 📄 as icons).
- **Design tokens** (color/spacing/radius/typography) — the approved direction becomes the
  source tokens for the app + `docs/decisions/` ADR.
- **States demonstrated**: loading/empty (transactions empty-state demo), validation (expense
  form error + inline hints), success (balanced-entry chip), permission-aware actions (locked
  "ثبت نهایی" and manager-only nav), unsaved-changes warning, toast feedback.
- **Accessible tabular alternatives** for charts («جدول دادهها» toggle).
- **Data coherence**: income sum = ۹۶٬۸۵۰٬۰۰۰ = 96.8M (chart totals), expense sum = ۶۱٬۳۴۰٬۰۰۰;
  transactions table sum = ۲۴۹٬۲۵۰٬۰۰۰; invoice math (125M + 15M − 7M = 133M; −50M prepaid
  = 83M balance) is exact — mirrors the ledger-reconciliation requirement.

## WCAG 2.2 AA fundamentals applied

- Contrast: every token pair checked (4.5:1+ for body text; 3:1+ for large/UI in both themes).
- Keyboard: all controls are real buttons/inputs; visible `:focus-visible` ring per direction.
- Labels: `aria-label` on icon-only buttons, `aria-describedby` on error/hint fields,
  `aria-pressed` on toggles, `role=group/radiogroup`, `aria-invalid` on the error field.
- Touch targets: ≥ 32px controls; mobile bottom-nav 58px tall.
- Reduced motion: global `prefers-reduced-motion` guard.
- Error association: field-level Persian error text under the offending input.

## Next step (checkpoint)

Per the project brief, production scaffolding must not start until a direction is approved.
Select one direction (or request changes) — the approved one will be turned into design tokens +
reusable components, then implementation proceeds in vertical slices per `../PLAN.md`.
