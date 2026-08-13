# قواعد حسابداری — Accounting Rules

The ledger is the source of truth. This document defines the rules and sample entries.
Status: **slices 1–2 implemented** (identity + ledger core); posting rules for
expenses/invoices/payments/funding land with slices 3–6.

## Fixed conventions

- **Unit:** integer Iranian rials only. Never binary floating point. UI enters/displays rial
  (ADR-0001). Exact conversion rule: **1 toman = 10 rials**; if toman input is ever offered it
  is converted exactly before persistence (`app/core/money.py`, covered by exact tests).
- **Double-entry accrual:** every posted business event creates a balanced journal entry
  (total debits = total credits, both > 0). Unbalanced entries are rejected by the posting
  service (`unbalanced_entry`) and by DB check constraints backstops
  (`ck_line_single_side`, `ck_line_non_negative`).
- **Immutability:** posted lines/entries have no update path; corrections use reversal entries
  (`void_entry` creates a mirror reversal linked via `reversal_of_id`). A reversal itself
  cannot be reversed.
- **Periods:** open/closed accounting periods (Solar Hijri year/month); posting into a closed
  period is rejected (`period_closed`); close = accountant/owner, reopen = **owner only**;
  every close/reopen is recorded in `period_events`.
- **References:** sequential per (company, jalali year, month) — `J-1405-0001` — generated
  race-safely via a locked `period_sequences` counter.
- **Idempotency:** optional `idempotency_key` on drafts; duplicates return the existing entry;
  a DB unique constraint backstops concurrent claims.
- **Reports:** derived from posted ledger entries only — never from separately maintained totals
  (implemented from slice 8).
- **Debit/credit convention:** assets and expenses increase on the **debit** side; liabilities,
  equity, and revenue increase on the **credit** side (standard). Documented with tests.
- **Tax/VAT, OCR, bank-statement import:** explicitly out of scope for the MVP.

## Chart of accounts (seeded, `seed_chart_of_accounts`)

| Code | Account | Type | Note |
|---|---|---|---|
| ۱۰۱ | صندوق | Asset | cash |
| ۱۰۲ | بانک — حساب جاری | Asset | bank |
| ۲۰۳ | حسابهای دریافتنی | Asset | receivables |
| ۲۰۴ | حسابهای پرداختنی | Liability | payables |
| ۳۰۱ | سرمایه مالک | Equity | owner capital |
| ۴۰۱ | درآمد فروش | Revenue | sales |
| ۴۰۲ | درآمد خدمات | Revenue | services |
| ۶۰۱ | هزینه اجاره | Expense | rent |
| ۶۰۲ | حقوق و دستمزد | Expense | payroll |
| ۶۰۳ | مواد اولیه و کالا | Expense | materials |
| ۶۰۴ | ارتباطات و اینترنت | Expense | comms |
| ۶۰۵ | حمل و سوخت | Expense | transport |
| ۶۰۶ | هزینههای عمومی | Expense | general |

Accounts are customizable (owner/accountant); system-seeded accounts cannot be renamed
(`account_system`).

## Sample entries (implemented via manual journals)

**Expense paid by bank transfer**
```
دکتر  ۶۰۳ مواد اولیه و کالا    ۴۸٬۵۰۰٬۰۰۰
بستانکار  ۱۰۲ بانک — حساب جاری     ۴۸٬۵۰۰٬۰۰۰
```

**Customer invoice (accrual sale)** — slice 4
```
دکتر  ۲۰۳ حسابهای دریافتنی        ۱۳۳٬۰۰۰٬۰۰۰
بستانکار  ۴۰۱ درآمد فروش             ۱۳۳٬۰۰۰٬۰۰۰
```

**Partial payment received** — slice 4
```
دکتر  ۱۰۲ بانک                      ۵۰٬۰۰۰٬۰۰۰
بستانکار  ۲۰۳ حسابهای دریافتنی         ۵۰٬۰۰۰٬۰۰۰
```

**Owner investment (not revenue)** — slice 6
```
دکتر  ۱۰۲ بانک                    ۴۰۰٬۰۰۰٬۰۰۰
بستانکار  ۳۰۱ سرمایه مالک            ۴۰۰٬۰۰۰٬۰۰۰
```

## Posting rules checklist

- ✅ Manual journals: accountant/owner create draft → validate → post (balanced, accounts
  active, period open); corrections via reversal (`void`).
- Expenses: `Draft → Posted → Paid`, `Void` via reversal after posting (slice 3).
- Supplier bills: `Draft → Open → Partially Paid → Paid → Void`; payable + expense on posting (slice 5).
- Customer invoices: `Draft → Issued → Partially Paid → Paid → Overdue → Void` (slice 4).
- Payments: receivable/payable + cash/bank reversal entries; partial payments supported; overpayment
  policy documented and tested (slice 4/5).
- Funding: explicit account mappings; investment/loan/grant never booked as revenue (slice 6).
- Cash-flow statement methodology documented and labeled clearly (slice 8).
