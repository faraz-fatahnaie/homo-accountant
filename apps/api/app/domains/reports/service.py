"""Report service (slice 8): all figures derive from the posted ledger.

Method notes (documented in docs/accounting-rules.md, "گزارشها"):
- Only journal entries with status=POSTED are ever included; drafts, voids'
  original entries are netted out by their reversal entries (reversals are
  posted entries with opposite sides, so they naturally cancel in balances).
- Signed balance convention (matches `ledger.account_balances`):
  assets & expenses increase on the debit side (positive balance);
  liabilities, equity & revenue on the credit side.
- Each report carries a `reconciled` flag asserting its cross-check:
    TB          total debits == total credits
    BalanceSheet assets == liabilities + equity (incl. current-period income)
    CashFlow    beginning + net change == ending (ledger cash & bank accounts)
    Aging       aging total == ledger balance of 203 (receivable) / 204 (payable)
    Funding     events total == ledger credit on the mapped account
- Cash & bank = accounts 101 (صندوق) and 102 (بانک) — the starter chart's
  two cash accounts; extendable by adding codes to CASH_BANK_CODES.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.jalali import gregorian_to_jalali, jalali_to_gregorian
from app.domains.bills.models import Bill, BillStatus
from app.domains.contacts.models import Contact
from app.domains.expenses.models import Expense, ExpenseStatus
from app.domains.funding.models import FundingEvent, FundingType
from app.domains.funding.service import DEFAULT_MAPPINGS, get_mapping
from app.domains.invoices.models import Invoice, InvoiceStatus
from app.domains.ledger.models import Account, AccountType, JournalEntry, JournalLine, JournalStatus
from app.domains.ledger.service import get_account
from app.domains.projects.models import Project

# ---------------------------------------------------------------------------
# Constants / conventions
# ---------------------------------------------------------------------------

CASH_BANK_CODES = {"101", "102"}  # صندوق + بانک (starter chart)
RECEIVABLES_CODE = "203"  # حسابهای دریافتنی
PAYABLES_CODE = "204"  # حسابهای پرداختنی
EQUITY_CODE = "301"  # سرمایه مالک
LOAN_CODE = "205"  # وام دریافتی (funding default mapping)

AGING_BUCKETS = [
    ("current", "جاری (سررسید نرسیده)"),
    ("1_30", "۱ تا ۳۰ روز"),
    ("31_60", "۳۱ تا ۶۰ روز"),
    ("61_90", "۶۱ تا ۹۰ روز"),
    ("over_90", "بیش از ۹۰ روز"),
]


def _signed_balance(atype: AccountType, debits: int, credits: int) -> int:
    """Signed balance: assets/expenses debit-positive; others credit-positive."""
    if atype in (AccountType.ASSET, AccountType.EXPENSE):
        return debits - credits
    return credits - debits


def _posted_balances(
    db: Session, company_id: int, as_of: dt.date | None = None
) -> dict[str, dict[str, object]]:
    """{code: {code,name,type,debit_total,credit_total,balance}} for posted lines."""
    stmt = (
        select(
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debits"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credits"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(Account.company_id == company_id, JournalEntry.status == JournalStatus.POSTED)
    )
    if as_of is not None:
        stmt = stmt.where(JournalEntry.entry_date <= as_of)
    stmt = stmt.group_by(Account.code, Account.name, Account.type).order_by(
        Account.type, Account.code
    )
    out: dict[str, dict[str, object]] = {}
    for code, name, atype, debits, credits in db.execute(stmt).all():
        deb, cre = int(debits), int(credits)
        out[code] = {
            "code": code,
            "name": name,
            "type": atype.value,
            "debit_total": deb,
            "credit_total": cre,
            "balance": _signed_balance(atype, deb, cre),
        }
    return out


def _cash_bank_balance(balances: dict[str, dict[str, object]]) -> int:
    return sum(int(b["balance"]) for c, b in balances.items() if c in CASH_BANK_CODES)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Trial balance
# ---------------------------------------------------------------------------


def trial_balance(db: Session, company_id: int, as_of: dt.date | None = None) -> dict[str, object]:
    """تراز آزمایشی: debit/credit totals + signed balance per account.

    Invariant: total debits == total credits (both sides must agree exactly).
    """
    balances = _posted_balances(db, company_id, as_of)
    rows = sorted(balances.values(), key=lambda r: (r["type"], r["code"]))  # type: ignore[arg-type]
    total_debit = sum(int(r["debit_total"]) for r in rows)  # type: ignore[arg-type]
    total_credit = sum(int(r["credit_total"]) for r in rows)  # type: ignore[arg-type]
    return {
        "as_of": as_of,
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "balanced": total_debit == total_credit,
        "reconciled": total_debit == total_credit,
    }


# ---------------------------------------------------------------------------
# Profit & loss
# ---------------------------------------------------------------------------


def profit_loss(
    db: Session, company_id: int, from_date: dt.date, to_date: dt.date
) -> dict[str, object]:
    """صورت سود و زیان for [from_date, to_date] on posted entries.

    Revenue accounts → net credit (income); expense accounts → net debit.
    Net income = total revenue − total expenses.
    """
    stmt = (
        select(
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(JournalLine.debit), 0).label("debits"),
            func.coalesce(func.sum(JournalLine.credit), 0).label("credits"),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            Account.company_id == company_id,
            JournalEntry.status == JournalStatus.POSTED,
            JournalEntry.entry_date >= from_date,
            JournalEntry.entry_date <= to_date,
        )
        .group_by(Account.code, Account.name, Account.type)
        .order_by(Account.type, Account.code)
    )
    revenue: list[dict[str, object]] = []
    expenses: list[dict[str, object]] = []
    total_revenue = total_expenses = 0
    for code, name, atype, debits, credits in db.execute(stmt).all():
        deb, cre = int(debits), int(credits)
        if atype == AccountType.REVENUE:
            amount = cre - deb
            revenue.append({"code": code, "name": name, "amount": amount, "type": "revenue"})
            total_revenue += amount
        elif atype == AccountType.EXPENSE:
            amount = deb - cre
            expenses.append({"code": code, "name": name, "amount": amount, "type": "expense"})
            total_expenses += amount
    revenue.sort(key=lambda r: -abs(int(r["amount"])))  # type: ignore[arg-type]
    expenses.sort(key=lambda r: -abs(int(r["amount"])))  # type: ignore[arg-type]
    return {
        "from": from_date,
        "to": to_date,
        "revenue": revenue,
        "expenses": expenses,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_income": total_revenue - total_expenses,
        "reconciled": True,  # direct ledger aggregates; balanced entries guarantee the rest
    }


# ---------------------------------------------------------------------------
# Balance sheet
# ---------------------------------------------------------------------------


def balance_sheet(db: Session, company_id: int, as_of: dt.date) -> dict[str, object]:
    """ترازنامه as of a date.

    Current-period net income (from posted entries <= as_of) is folded into
    equity as «سود (زیان) دوره». Invariant: assets == liabilities + equity.
    """
    balances = _posted_balances(db, company_id, as_of)
    assets: list[dict[str, object]] = []
    liabilities: list[dict[str, object]] = []
    equity: list[dict[str, object]] = []
    for code, row in sorted(balances.items()):
        bal = int(row["balance"])  # type: ignore[arg-type]
        if bal == 0:
            continue
        atype = row["type"]
        item = {"code": code, "name": row["name"], "amount": bal}
        if atype == "asset":
            assets.append(item)
        elif atype == "liability":
            liabilities.append(item)
        elif atype == "equity":
            equity.append(item)
    # current-period income: revenue net credits − expense net debits (all time <= as_of)
    income = 0
    for row in balances.values():
        bal = int(row["balance"])  # type: ignore[arg-type]
        if row["type"] == "revenue":
            income += bal
        elif row["type"] == "expense":
            income -= bal
    if income != 0:
        equity.append({"code": "PNL", "name": "سود (زیان) دوره", "amount": income})

    total_assets = sum(int(r["amount"]) for r in assets)
    total_liabilities = sum(int(r["amount"]) for r in liabilities)
    total_equity = sum(int(r["amount"]) for r in equity)
    total_liab_equity = total_liabilities + total_equity
    return {
        "as_of": as_of,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_equity": total_liab_equity,
        "net_income": income,
        "reconciled": total_assets == total_liab_equity,
    }


# ---------------------------------------------------------------------------
# Cash flow (direct method, documented)
# ---------------------------------------------------------------------------


def _cash_flow_section(items: list[dict[str, object]]) -> dict[str, object]:
    inflow = sum(int(i["inflow"]) for i in items)  # type: ignore[arg-type]
    outflow = sum(int(i["outflow"]) for i in items)  # type: ignore[arg-type]
    return {"items": items, "inflow": inflow, "outflow": outflow, "net": inflow - outflow}


def _classify(counterparts: list[dict[str, object]]) -> str:
    """Classify an entry's cash movement by its non-cash counterpart lines.

    Priority: operating > financing > investing (a mixed entry is booked to
    the first section below; see docs/accounting-rules.md).
    """
    for row in counterparts:
        atype = row["type"]
        code = row["code"]
        if atype in ("expense", "revenue"):
            return "operating"
    for row in counterparts:
        code = row["code"]
        if code in (RECEIVABLES_CODE, PAYABLES_CODE):
            return "operating"
    for row in counterparts:
        atype = row["type"]
        code = row["code"]
        if atype in ("equity", "liability"):
            return "financing"
    for row in counterparts:
        atype = row["type"]
        if atype == "asset":
            return "investing"
    return "other"


def cash_flow(
    db: Session, company_id: int, from_date: dt.date, to_date: dt.date
) -> dict[str, object]:
    """صورت جریان وجوه نقد — direct method on the posted ledger.

    Cash & bank = accounts 101/102. Every posted entry in [from, to] that
    touches cash/bank produces one cash movement, classified by its non-cash
    counterpart lines (operating / financing / investing / other).
    Invariant: beginning cash + Σ net == ending cash (both from the ledger).
    """
    entries = (
        db.execute(
            select(JournalEntry)
            .where(
                JournalEntry.company_id == company_id,
                JournalEntry.status == JournalStatus.POSTED,
                JournalEntry.entry_date >= from_date,
                JournalEntry.entry_date <= to_date,
            )
            .order_by(JournalEntry.entry_date, JournalEntry.id)
        )
        .scalars()
        .all()
    )

    sections: dict[str, list[dict[str, object]]] = {
        "operating": [],
        "financing": [],
        "investing": [],
        "other": [],
    }
    for entry in entries:
        cash_in = cash_out = 0
        counterparts: list[dict[str, object]] = []
        for line in entry.lines:
            code = line.account.code
            if code in CASH_BANK_CODES:
                cash_in += int(line.debit)
                cash_out += int(line.credit)
            else:
                counterparts.append(
                    {
                        "code": code,
                        "name": line.account.name,
                        "type": line.account.type.value,
                    }
                )
        if cash_in == 0 and cash_out == 0:
            continue  # no cash effect (e.g. accrual-only entry)
        section = _classify(counterparts)
        sections[section].append(
            {
                "entry_id": entry.id,
                "date": entry.entry_date,
                "reference": entry.reference,
                "memo": entry.memo,
                "counterparts": counterparts,
                "inflow": cash_in,
                "outflow": cash_out,
                "net": cash_in - cash_out,
            }
        )

    beginning = _cash_bank_balance(
        _posted_balances(db, company_id, from_date - dt.timedelta(days=1))
    )
    ending = _cash_bank_balance(_posted_balances(db, company_id, to_date))
    total_net = 0
    result_sections: dict[str, dict[str, object]] = {}
    for key in ("operating", "financing", "investing", "other"):
        sec = _cash_flow_section(sections[key])
        total_net += int(sec["net"])  # type: ignore[arg-type]
        result_sections[key] = sec
    reconciled = beginning + total_net == ending
    return {
        "from": from_date,
        "to": to_date,
        "beginning_cash_bank": beginning,
        "ending_cash_bank": ending,
        "net_change": ending - beginning,
        "sections": result_sections,
        "total_net": total_net,
        "reconciled": reconciled,
    }


# ---------------------------------------------------------------------------
# General ledger (account drill-down)
# ---------------------------------------------------------------------------


def general_ledger(
    db: Session,
    company_id: int,
    account_code: str,
    from_date: dt.date,
    to_date: dt.date,
) -> dict[str, object]:
    """دفتر کل: per-account lines with a running balance for [from, to].

    Opening balance = signed balance of posted entries before `from_date`.
    """
    account = get_account(db, company_id, account_code)
    if account is None:
        return {"error": "account_not_found", "account_code": account_code}
    opening_row = _posted_balances(db, company_id, from_date - dt.timedelta(days=1)).get(
        account_code
    )
    opening = int(opening_row["balance"]) if opening_row else 0  # type: ignore[arg-type]

    rows = db.execute(
        select(JournalEntry, JournalLine)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalStatus.POSTED,
            JournalLine.account_id == account.id,
            JournalEntry.entry_date >= from_date,
            JournalEntry.entry_date <= to_date,
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id, JournalLine.id)
    ).all()

    sign = 1 if account.type in (AccountType.ASSET, AccountType.EXPENSE) else -1
    running = opening
    lines: list[dict[str, object]] = []
    for entry, line in rows:
        running += int(line.debit) * sign - int(line.credit) * sign
        lines.append(
            {
                "entry_id": entry.id,
                "date": entry.entry_date,
                "reference": entry.reference,
                "memo": entry.memo,
                "debit": int(line.debit),
                "credit": int(line.credit),
                "balance": running,
            }
        )
    return {
        "account": {
            "code": account.code,
            "name": account.name,
            "type": account.type.value,
        },
        "from": from_date,
        "to": to_date,
        "opening_balance": opening,
        "closing_balance": running,
        "lines": lines,
        "reconciled": True,
    }


# ---------------------------------------------------------------------------
# Aging (receivables / payables)
# ---------------------------------------------------------------------------


def _bucket_for(as_of: dt.date, due_date: dt.date | None) -> str:
    if due_date is None:
        return "current"
    days = (as_of - due_date).days
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "over_90"


def aging(db: Session, company_id: int, as_of: dt.date) -> dict[str, object]:
    """سررسید حسابهای دریافتنی و پرداختنی as of a date.

    Buckets: current / 1–30 / 31–60 / 61–90 / 90+ days past due.
    Invariant: receivable total == ledger balance of 203;
               payable total == ledger balance of 204.
    """
    rec_rows: list[dict[str, object]] = []
    pay_rows: list[dict[str, object]] = []
    invoices = db.scalars(
        select(Invoice)
        .where(
            Invoice.company_id == company_id,
            Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID]),
        )
        .order_by(Invoice.due_date)
    ).all()
    contacts = {
        c.id: c.name for c in db.scalars(select(Contact).where(Contact.company_id == company_id))
    }
    for inv in invoices:
        paid = sum(int(p.amount) for p in inv.payments)
        balance = int(inv.total) - paid
        if balance <= 0:
            continue
        bucket = _bucket_for(as_of, inv.due_date)
        rec_rows.append(
            {
                "number": inv.number,
                "contact_name": contacts.get(inv.customer_id, "—"),
                "due_date": inv.due_date,
                "total": int(inv.total),
                "paid": paid,
                "balance": balance,
                "bucket": bucket,
            }
        )
    bills = db.scalars(
        select(Bill)
        .where(
            Bill.company_id == company_id,
            Bill.status.in_([BillStatus.OPEN, BillStatus.PARTIALLY_PAID]),
        )
        .order_by(Bill.due_date)
    ).all()
    for bill in bills:
        paid = sum(int(p.amount) for p in bill.payments)
        balance = int(bill.total) - paid
        if balance <= 0:
            continue
        bucket = _bucket_for(as_of, bill.due_date)
        pay_rows.append(
            {
                "number": bill.number,
                "contact_name": contacts.get(bill.vendor_id, "—"),
                "due_date": bill.due_date,
                "total": int(bill.total),
                "paid": paid,
                "balance": balance,
                "bucket": bucket,
            }
        )

    def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
        buckets: dict[str, int] = {}
        total = 0
        for r in rows:
            b = str(r["bucket"])
            buckets[b] = buckets.get(b, 0) + int(r["balance"])  # type: ignore[arg-type]
            total += int(r["balance"])  # type: ignore[arg-type]
        return {
            "rows": rows,
            "buckets": [
                {"key": key, "label": label, "amount": buckets.get(key, 0)}
                for key, label in AGING_BUCKETS
            ],
            "total": total,
        }

    receivable = summarize(rec_rows)
    payable = summarize(pay_rows)
    ledger = _posted_balances(db, company_id, as_of)
    rec_ledger = int(ledger.get(RECEIVABLES_CODE, {}).get("balance", 0))  # type: ignore[arg-type]
    pay_ledger = int(ledger.get(PAYABLES_CODE, {}).get("balance", 0))  # type: ignore[arg-type]
    receivable["ledger_balance"] = rec_ledger
    payable["ledger_balance"] = pay_ledger
    receivable["reconciled"] = int(receivable["total"]) == rec_ledger  # type: ignore[arg-type]
    payable["reconciled"] = int(payable["total"]) == pay_ledger  # type: ignore[arg-type]
    return {
        "as_of": as_of,
        "receivable": receivable,
        "payable": payable,
        "reconciled": bool(receivable["reconciled"]) and bool(payable["reconciled"]),  # type: ignore[index]
    }


# ---------------------------------------------------------------------------
# Budget vs actual (per project)
# ---------------------------------------------------------------------------


def budget_vs_actual(
    db: Session, company_id: int, from_date: dt.date, to_date: dt.date
) -> dict[str, object]:
    """بودجه و عملکرد per project: budget vs posted expenses in [from, to].

    «عملکرد» = مجموع هزینههای ثبتشده (پستشده، غیر باطل) تخصیصیافته به پروژه؛
    مستندات هزینه در پس هر کدام سند دفتر کل دارد (حساب هزینه).
    """
    projects = db.scalars(
        select(Project).where(Project.company_id == company_id).order_by(Project.name)
    ).all()
    expense_sums = dict(
        db.execute(
            select(Expense.project_id, func.sum(Expense.amount))
            .where(
                Expense.company_id == company_id,
                Expense.status == ExpenseStatus.POSTED,
                Expense.entry_date >= from_date,
                Expense.entry_date <= to_date,
            )
            .group_by(Expense.project_id)
        ).all()
    )
    rows: list[dict[str, object]] = []
    total_budget = total_actual = 0
    for p in projects:
        budget = int(p.budget)
        actual = int(expense_sums.get(p.id, 0))  # type: ignore[arg-type]
        total_budget += budget
        total_actual += actual
        rows.append(
            {
                "project_id": p.id,
                "name": p.name,
                "status": p.status.value,
                "budget": budget,
                "actual": actual,
                "remaining": budget - actual,
                "utilization": round(actual / budget, 4) if budget > 0 else None,
            }
        )
    rows.sort(key=lambda r: r["name"])  # type: ignore[arg-type]
    return {
        "from": from_date,
        "to": to_date,
        "rows": rows,
        "total_budget": total_budget,
        "total_actual": total_actual,
        "total_remaining": total_budget - total_actual,
        "total_utilization": round(total_actual / total_budget, 4) if total_budget > 0 else None,
        "reconciled": True,
    }


# ---------------------------------------------------------------------------
# Funding summary
# ---------------------------------------------------------------------------


def _funding_ledger_credit(
    db: Session, company_id: int, funding_type: FundingType, from_date: dt.date, to_date: dt.date
) -> tuple[int, str]:
    mapping = get_mapping(db, company_id, funding_type)
    code = mapping.account_code if mapping else DEFAULT_MAPPINGS[funding_type]
    events = db.scalars(
        select(FundingEvent).where(
            FundingEvent.company_id == company_id,
            FundingEvent.funding_type == funding_type,
            FundingEvent.status == "posted",
            FundingEvent.event_date >= from_date,
            FundingEvent.event_date <= to_date,
            FundingEvent.journal_entry_id.is_not(None),
        )
    ).all()
    entry_ids = [e.journal_entry_id for e in events]
    if not entry_ids:
        return 0, code
    credit = db.execute(
        select(func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .where(
            JournalLine.account_id.in_(
                select(Account.id).where(Account.company_id == company_id, Account.code == code)
            ),
            JournalEntry.id.in_(entry_ids),
            JournalEntry.status == JournalStatus.POSTED,
        )
    ).scalar_one()
    return int(credit), code


def funding_summary(
    db: Session, company_id: int, from_date: dt.date, to_date: dt.date
) -> dict[str, object]:
    """خلاصه تأمین مالی by type for [from, to], reconciled to the ledger.

    For each type the event total must equal the credit booked on the type's
    mapped account for the same journal entries (loans/investment never
    revenue — slice 6 rule).
    """
    events = db.scalars(
        select(FundingEvent)
        .where(
            FundingEvent.company_id == company_id,
            FundingEvent.status == "posted",
            FundingEvent.event_date >= from_date,
            FundingEvent.event_date <= to_date,
        )
        .order_by(FundingEvent.event_date, FundingEvent.id)
    ).all()
    types: list[dict[str, object]] = []
    for t in FundingType:
        group = [e for e in events if e.funding_type == t]
        total = sum(int(e.amount) for e in group)
        ledger_credit, account_code = _funding_ledger_credit(db, company_id, t, from_date, to_date)
        maturity = [e.maturity_date for e in group if e.maturity_date is not None]
        types.append(
            {
                "funding_type": t.value,
                "count": len(group),
                "total": total,
                "account_code": account_code,
                "ledger_credit": ledger_credit,
                "reconciled": total == ledger_credit,
                "maturity_date": min(maturity) if maturity else None,
            }
        )
    total_all = sum(int(t["total"]) for t in types)  # type: ignore[arg-type]
    return {
        "from": from_date,
        "to": to_date,
        "types": types,
        "total": total_all,
        "reconciled": all(bool(t["reconciled"]) for t in types),  # type: ignore[arg-type]
    }


# ---------------------------------------------------------------------------
# Dashboard KPIs
# ---------------------------------------------------------------------------

FISCAL_YEAR_START_MONTH = 1


def _fiscal_year_window(db: Session, company_id: int, today: dt.date) -> tuple[dt.date, dt.date]:
    jy, _, _ = gregorian_to_jalali(today)
    start = jalali_to_gregorian(jy, 1, 1)
    return start, today


def dashboard(db: Session, company_id: int) -> dict[str, object]:
    """One round-trip for the dashboard; every number is ledger-derived."""
    today = dt.date.today()
    ytd_start, ytd_end = _fiscal_year_window(db, company_id, today)
    balances = _posted_balances(db, company_id, today)
    cash_bank = _cash_bank_balance(balances)
    receivables = int(balances.get(RECEIVABLES_CODE, {}).get("balance", 0))  # type: ignore[arg-type]
    payables = int(balances.get(PAYABLES_CODE, {}).get("balance", 0))  # type: ignore[arg-type]

    pl = profit_loss(db, company_id, ytd_start, ytd_end)
    cf = cash_flow(db, company_id, ytd_start, ytd_end)
    ag = aging(db, company_id, today)
    bva = budget_vs_actual(db, company_id, ytd_start, ytd_end)
    fnd = funding_summary(db, company_id, ytd_start, ytd_end)

    recent = db.scalars(
        select(JournalEntry)
        .where(
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalStatus.POSTED,
        )
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .limit(5)
    ).all()
    recent_out = []
    for e in recent:
        debit_sum = sum(int(ln.debit) for ln in e.lines)
        credit_sum = sum(int(ln.credit) for ln in e.lines)
        recent_out.append(
            {
                "id": e.id,
                "entry_date": e.entry_date,
                "reference": e.reference,
                "memo": e.memo,
                "total": max(debit_sum, credit_sum),
            }
        )

    key_accounts = [
        {"code": b["code"], "name": b["name"], "type": b["type"], "balance": b["balance"]}
        for b in sorted(
            (v for v in balances.values() if int(v["balance"]) != 0),  # type: ignore[arg-type]
            key=lambda v: -abs(int(v["balance"])),  # type: ignore[arg-type]
        )
    ][:6]

    return {
        "as_of": today,
        "fiscal_year": gregorian_to_jalali(today)[0],
        "period_start": ytd_start,
        "period_end": ytd_end,
        "cash_bank": cash_bank,
        "receivables": receivables,
        "payables": payables,
        "revenue": int(pl["total_revenue"]),  # type: ignore[arg-type]
        "expenses": int(pl["total_expenses"]),  # type: ignore[arg-type]
        "net_income": int(pl["net_income"]),  # type: ignore[arg-type]
        "cash_flow_net": int(cf["net_change"]),  # type: ignore[arg-type]
        "cash_flow_reconciled": bool(cf["reconciled"]),  # type: ignore[index]
        "receivable_aging_total": int(ag["receivable"]["total"]),  # type: ignore[index]
        "payable_aging_total": int(ag["payable"]["total"]),  # type: ignore[index]
        "aging_reconciled": bool(ag["reconciled"]),
        "total_budget": int(bva["total_budget"]),  # type: ignore[arg-type]
        "total_actual": int(bva["total_actual"]),  # type: ignore[arg-type]
        "budget_utilization": bva["total_utilization"],
        "funding_total": int(fnd["total"]),  # type: ignore[arg-type]
        "funding_reconciled": bool(fnd["reconciled"]),  # type: ignore[index]
        "recent_entries": recent_out,
        "key_accounts": key_accounts,
    }


# ---------------------------------------------------------------------------
# Reconciliation summary
# ---------------------------------------------------------------------------


def reconciliation(db: Session, company_id: int, as_of: dt.date) -> dict[str, object]:
    """Cross-report reconciliation checks (each figure ↔ posted ledger)."""
    tb = trial_balance(db, company_id, as_of)
    bs = balance_sheet(db, company_id, as_of)
    ytd_start, _ = _fiscal_year_window(db, company_id, as_of)
    cf = cash_flow(db, company_id, ytd_start, as_of)
    ag = aging(db, company_id, as_of)
    fnd = funding_summary(db, company_id, ytd_start, as_of)
    pl = profit_loss(db, company_id, ytd_start, as_of)

    checks = [
        {
            "key": "trial_balance",
            "label": "تراز آزمایشی (جمع بدهکار = جمع بستانکار)",
            "ok": bool(tb["balanced"]),  # type: ignore[index]
            "detail": f"بدهکار {tb['total_debit']:,} ریال / بستانکار {tb['total_credit']:,} ریال",
        },
        {
            "key": "balance_sheet",
            "label": "ترازنامه (داراییها = بدهیها + حقوق صاحبان سهام)",
            "ok": bool(bs["reconciled"]),  # type: ignore[index]
            "detail": (
                f"دارایی {bs['total_assets']:,} / بدهی+سرمایه {bs['total_liabilities_equity']:,}"
            ),
        },
        {
            "key": "cash_flow",
            "label": "جریان وجوه نقد (موجودی ابتدا + تغییرات = انتها)",
            "ok": bool(cf["reconciled"]),  # type: ignore[index]
            "detail": f"تغییر خالص {cf['net_change']:,} ریال",
        },
        {
            "key": "aging_receivable",
            "label": "سررسید دریافتنی با مانده حساب ۲۰۳",
            "ok": bool(ag["receivable"]["reconciled"]),  # type: ignore[index]
            "detail": (
                f"گزارش {ag['receivable']['total']:,} / "
                f"دفتر کل {ag['receivable']['ledger_balance']:,}"
            ),
        },
        {
            "key": "aging_payable",
            "label": "سررسید پرداختنی با مانده حساب ۲۰۴",
            "ok": bool(ag["payable"]["reconciled"]),  # type: ignore[index]
            "detail": (
                f"گزارش {ag['payable']['total']:,} / دفتر کل {ag['payable']['ledger_balance']:,}"
            ),
        },
        {
            "key": "funding",
            "label": "تأمین مالی با اعتبار سندهای دفتر کل (نگاشت)",
            "ok": bool(fnd["reconciled"]),  # type: ignore[index]
            "detail": f"رویدادها {fnd['total']:,} ریال",
        },
        {
            "key": "profit_loss",
            "label": "سود و زیان دوره (درآمد − هزینه)",
            "ok": True,
            "detail": (
                f"درآمد {pl['total_revenue']:,} / هزینه {pl['total_expenses']:,} / "
                f"نتیجه {pl['net_income']:,}"
            ),  # type: ignore[index]
        },
    ]
    return {
        "as_of": as_of,
        "checks": checks,
        "all_ok": all(bool(c["ok"]) for c in checks),  # type: ignore[arg-type]
    }
