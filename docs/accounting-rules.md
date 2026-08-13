# قواعد حسابداری — Accounting Rules

The ledger is the source of truth. This document defines the rules and sample entries;
it grows as each accounting slice lands. Status: charter + fixed decisions (slice 1);
posting rules for expenses/invoices/payments/funding land with slices 3–6.

## Fixed conventions

- **Unit:** integer Iranian rials only. Never binary floating point. UI enters/displays rial
  (ADR-0001). Exact conversion rule: **1 toman = 10 rials**; if toman input is ever offered it
  is converted exactly before persistence. Documented for future use; not exposed in the MVP UI.
- **Double-entry accrual:** every posted business event creates a balanced journal entry
  (total debits = total credits). Unbalanced entries are rejected by the posting service and by
  a database constraint backstop (slice 2).
- **Immutability:** posted lines are immutable. Corrections use reversal/adjusting entries —
  never silent edits or deletion of posted history.
- **Periods:** open/closed accounting periods; posting into a closed period is rejected;
  reopening is owner-controlled and recorded in the activity trail.
- **Reports:** derived from posted ledger entries only — never from separately maintained totals.
- **Debit/credit convention:** assets and expenses increase on the **debit** side; liabilities,
  equity, and revenue increase on the **credit** side (standard). Documented with tests in slice 2.
- **Tax/VAT, OCR, bank-statement import:** explicitly out of scope for the MVP.

## Starter chart of accounts (to be seeded in slice 2)

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

## Sample entries (slice 2 targets)

**Expense paid by bank transfer**
```
دکتر  ۶۰۳ مواد اولیه و کالا    ۴۸٬۵۰۰٬۰۰۰
بستانکار  ۱۰۲ بانک — حساب جاری     ۴۸٬۵۰۰٬۰۰۰
```

**Customer invoice (accrual sale)**
```
دکتر  ۲۰۳ حسابهای دریافتنی        ۱۳۳٬۰۰۰٬۰۰۰
بستانکار  ۴۰۱ درآمد فروش             ۱۳۳٬۰۰۰٬۰۰۰
```

**Partial payment received**
```
دکتر  ۱۰۲ بانک                      ۵۰٬۰۰۰٬۰۰۰
بستانکار  ۲۰۳ حسابهای دریافتنی         ۵۰٬۰۰۰٬۰۰۰
```

**Owner investment (not revenue)**
```
دکتر  ۱۰۲ بانک                    ۴۰۰٬۰۰۰٬۰۰۰
بستانکار  ۳۰۱ سرمایه مالک            ۴۰۰٬۰۰۰٬۰۰۰
```

## Posting rules checklist (implemented per slice)

- Expenses: `Draft → Posted → Paid`, `Void` via reversal after posting (slice 3).
- Supplier bills: `Draft → Open → Partially Paid → Paid → Void`; payable + expense on posting (slice 5).
- Customer invoices: `Draft → Issued → Partially Paid → Paid → Overdue → Void` (slice 4).
- Payments: receivable/payable + cash/bank reversal entries; partial payments supported; overpayment
  policy documented and tested (slice 4/5).
- Funding: explicit account mappings; investment/loan/grant never booked as revenue (slice 6).
- Cash-flow statement methodology will be documented and labeled clearly (slice 8).
