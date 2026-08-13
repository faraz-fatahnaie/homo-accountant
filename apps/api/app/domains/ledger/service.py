"""Ledger service: chart of accounts, journal posting, periods.

Invariants enforced here (and backstopped by DB constraints):
- Every posted entry balances: total debits == total credits (and > 0).
- Posted entries are immutable; corrections use reversal entries.
- Posting into a closed period is rejected.
- References are sequential per (company, jalali year, month) and race-safe.
- Idempotency keys prevent duplicate postings.
All mutations happen inside a single DB transaction.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.jalali import entry_period, jalali_to_gregorian
from app.domains.ledger.models import (
    Account,
    AccountingPeriod,
    AccountType,
    JournalEntry,
    JournalLine,
    JournalStatus,
    PeriodAction,
    PeriodEvent,
    PeriodSequence,
    PeriodStatus,
)

logger = logging.getLogger(__name__)


class LedgerError(Exception):
    """Business-rule violation (mapped to 422/400 in routes)."""

    def __init__(self, message: str, code: str = "ledger_error", status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------

STARTER_CHART: list[tuple[str, str, AccountType]] = [
    ("101", "صندوق", AccountType.ASSET),
    ("102", "بانک — حساب جاری", AccountType.ASSET),
    ("203", "حسابهای دریافتنی", AccountType.ASSET),
    ("204", "حسابهای پرداختنی", AccountType.LIABILITY),
    ("301", "سرمایه مالک", AccountType.EQUITY),
    ("401", "درآمد فروش", AccountType.REVENUE),
    ("402", "درآمد خدمات", AccountType.REVENUE),
    ("601", "هزینه اجاره", AccountType.EXPENSE),
    ("602", "حقوق و دستمزد", AccountType.EXPENSE),
    ("603", "مواد اولیه و کالا", AccountType.EXPENSE),
    ("604", "ارتباطات و اینترنت", AccountType.EXPENSE),
    ("605", "حمل و سوخت", AccountType.EXPENSE),
    ("606", "هزینههای عمومی", AccountType.EXPENSE),
]


def seed_chart_of_accounts(db: Session, company_id: int) -> int:
    """Create the starter chart if not present; returns count created."""
    existing = set(db.scalars(select(Account.code).where(Account.company_id == company_id)))
    created = 0
    for code, name, atype in STARTER_CHART:
        if code in existing:
            continue
        db.add(Account(company_id=company_id, code=code, name=name, type=atype, is_system=True))
        created += 1
    db.flush()
    return created


def list_accounts(db: Session, company_id: int) -> list[Account]:
    return list(
        db.scalars(select(Account).where(Account.company_id == company_id).order_by(Account.code))
    )


def account_balances(db: Session, company_id: int) -> list[dict[str, object]]:
    """Signed balances per account from POSTED journal lines only.

    Sign convention: assets & expenses carry a positive balance on the debit
    side; liabilities, equity & revenue on the credit side. Drafts are never
    included — balances always reconcile to the posted ledger.
    """
    rows = db.execute(
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
            JournalEntry.company_id == company_id,
            JournalEntry.status == JournalStatus.POSTED,
        )
        .group_by(Account.id, Account.code, Account.name, Account.type)
        .order_by(Account.code)
    ).all()

    result: list[dict[str, object]] = []
    for code, name, atype, debits, credits in rows:
        if atype in (AccountType.ASSET, AccountType.EXPENSE):
            balance = int(debits) - int(credits)
        else:
            balance = int(credits) - int(debits)
        result.append(
            {
                "code": code,
                "name": name,
                "type": atype.value,
                "debit_total": int(debits),
                "credit_total": int(credits),
                "balance": balance,
            }
        )
    return result


def cash_and_bank_balance(db: Session, company_id: int) -> int:
    """موجودی نقد و بانک = مانده حساب‌های ۱۰۱ (صندوق) و ۱۰۲ (بانک)."""
    total = 0
    for b in account_balances(db, company_id):
        if b["code"] in {"101", "102"} and isinstance(b["balance"], int):
            total += b["balance"]
    return total


def get_account(db: Session, company_id: int, code: str) -> Account | None:
    return db.scalar(select(Account).where(Account.company_id == company_id, Account.code == code))


def create_account(
    db: Session, company_id: int, code: str, name: str, atype: AccountType, parent_code: str | None
) -> Account:
    if get_account(db, company_id, code) is not None:
        raise LedgerError(
            "حسابی با این کد از قبل وجود دارد", code="account_code_taken", status_code=409
        )
    parent_id: int | None = None
    if parent_code:
        parent = get_account(db, company_id, parent_code)
        if parent is None:
            raise LedgerError("کد حساب والد نامعتبر است", code="account_parent_missing")
        parent_id = parent.id
    account = Account(company_id=company_id, code=code, name=name, type=atype, parent_id=parent_id)
    db.add(account)
    db.flush()
    logger.info("account created", extra={"code": code, "type": atype.value})
    return account


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------


def get_period(db: Session, company_id: int, year: int, month: int) -> AccountingPeriod:
    period = db.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.company_id == company_id,
            AccountingPeriod.year == year,
            AccountingPeriod.month == month,
        )
    )
    if period is None:
        period = AccountingPeriod(company_id=company_id, year=year, month=month)
        db.add(period)
        db.flush()
    return period


def list_periods(db: Session, company_id: int) -> list[AccountingPeriod]:
    return list(
        db.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.company_id == company_id)
            .order_by(AccountingPeriod.year, AccountingPeriod.month)
        )
    )


def close_period(db: Session, period_id: int, actor_id: int) -> AccountingPeriod:
    period = db.get(AccountingPeriod, period_id)
    if period is None:
        raise LedgerError("دوره حسابداری یافت نشد", code="period_missing", status_code=404)
    if period.status == PeriodStatus.CLOSED:
        raise LedgerError("دوره از قبل بسته شده است", code="period_already_closed")
    now = dt.datetime.now(dt.UTC)
    period.status = PeriodStatus.CLOSED
    period.closed_at = now
    period.closed_by_id = actor_id
    db.add(PeriodEvent(period_id=period.id, action=PeriodAction.CLOSE, actor_id=actor_id))
    db.flush()
    logger.info("period closed", extra={"period_id": period.id, "by": actor_id})
    return period


def reopen_period(db: Session, period_id: int, actor_id: int) -> AccountingPeriod:
    period = db.get(AccountingPeriod, period_id)
    if period is None:
        raise LedgerError("دوره حسابداری یافت نشد", code="period_missing", status_code=404)
    if period.status == PeriodStatus.OPEN:
        raise LedgerError("دوره باز است", code="period_already_open")
    now = dt.datetime.now(dt.UTC)
    period.status = PeriodStatus.OPEN
    period.reopened_at = now
    period.reopened_by_id = actor_id
    db.add(PeriodEvent(period_id=period.id, action=PeriodAction.REOPEN, actor_id=actor_id))
    db.flush()
    logger.info("period reopened", extra={"period_id": period.id, "by": actor_id})
    return period


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


def create_draft_entry(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    entry_date: dt.date,
    memo: str,
    lines: list[tuple[str, int, int]],  # (account_code, debit, credit)
    idempotency_key: str | None = None,
) -> JournalEntry:
    if idempotency_key:
        existing = db.scalar(
            select(JournalEntry).where(JournalEntry.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
    entry = JournalEntry(
        company_id=company_id,
        entry_date=entry_date,
        memo=memo.strip(),
        status=JournalStatus.DRAFT,
        created_by_id=actor_id,
        idempotency_key=idempotency_key,
    )
    for code, debit, credit in lines:
        account = get_account(db, company_id, code)
        if account is None:
            raise LedgerError(f"حساب با کد {code} یافت نشد", code="account_missing")
        if not account.is_active:
            raise LedgerError(f"حساب {code} غیرفعال است", code="account_inactive")
        if (debit > 0) == (credit > 0):
            raise LedgerError(
                "هر ردیف سند باید دقیقاً یک سمت (بدهکار یا بستانکار) بیشتر از صفر داشته باشد",
                code="line_invalid",
            )
        entry.lines.append(JournalLine(account_id=account.id, debit=debit, credit=credit))
    db.add(entry)
    db.flush()
    return entry


def _next_reference(db: Session, company_id: int, year: int, month: int) -> str:
    """Race-safe sequential reference per (company, jalali year, month)."""
    seq = db.scalar(
        select(PeriodSequence).where(
            PeriodSequence.company_id == company_id,
            PeriodSequence.year == year,
            PeriodSequence.month == month,
        )
    )
    if seq is None:
        seq = PeriodSequence(company_id=company_id, year=year, month=month, last_number=0)
        db.add(seq)
        db.flush()
    # Lock the row for the remainder of the transaction (safe sequencing).
    db.execute(select(PeriodSequence.id).where(PeriodSequence.id == seq.id).with_for_update())
    seq.last_number += 1
    db.flush()
    return f"J-{year}-{seq.last_number:04d}"


def _assert_balanced(lines: list[JournalLine]) -> tuple[int, int]:
    total_debit = sum(line.debit for line in lines)
    total_credit = sum(line.credit for line in lines)
    if total_debit <= 0 or total_credit <= 0 or total_debit != total_credit:
        raise LedgerError(
            "سند نامتوازن است؛ جمع بدهکار و بستانکار باید برابر و بیشتر از صفر باشد",
            code="unbalanced_entry",
        )
    return total_debit, total_credit


def post_entry(db: Session, entry_id: int, actor_id: int) -> JournalEntry:
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise LedgerError("سند یافت نشد", code="entry_missing", status_code=404)
    if entry.status == JournalStatus.POSTED:
        # Idempotent replay: an already-posted entry carrying an idempotency
        # key is returned as-is instead of being treated as an error.
        if entry.idempotency_key:
            return entry
        raise LedgerError("سند از قبل ثبت شده است", code="entry_already_posted")
    # Idempotency: if a posted entry already carries the same key, return it.
    if entry.idempotency_key:
        dup = db.scalar(
            select(JournalEntry).where(
                JournalEntry.idempotency_key == entry.idempotency_key,
                JournalEntry.status == JournalStatus.POSTED,
            )
        )
        if dup is not None and dup.id != entry.id:
            return dup

    _assert_balanced(entry.lines)

    # Period gate: no posting into a closed period.
    year, month = entry_period(entry.entry_date)
    period = get_period(db, entry.company_id, year, month)
    if period.status == PeriodStatus.CLOSED:
        raise LedgerError(
            "دوره حسابداری مربوط به این سند بسته است؛ "
            "ابتدا دوره را باز کنید یا تاریخ سند را تغییر دهید",
            code="period_closed",
        )

    entry.reference = _next_reference(db, entry.company_id, year, month)
    entry.status = JournalStatus.POSTED
    entry.posted_by_id = actor_id
    entry.posted_at = dt.datetime.now(dt.UTC)
    db.flush()
    logger.info(
        "entry posted",
        extra={"entry_id": entry.id, "reference": entry.reference, "by": actor_id},
    )
    return entry


def void_entry(db: Session, entry_id: int, actor_id: int, memo: str | None = None) -> JournalEntry:
    """Create + post a reversal entry for a posted entry (never edits it)."""
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise LedgerError("سند یافت نشد", code="entry_missing", status_code=404)
    if entry.status != JournalStatus.POSTED:
        raise LedgerError("فقط سند ثبتشده را میتوان برگشت زد", code="entry_not_posted")
    if entry.reversal_of_id is not None:
        raise LedgerError("این سند خودش یک سند برگشتی است", code="entry_is_reversal")

    reversed_lines = [(line.account.code, line.credit, line.debit) for line in entry.lines]
    reversal = create_draft_entry(
        db,
        company_id=entry.company_id,
        actor_id=actor_id,
        entry_date=entry.entry_date,
        memo=memo or ("برگشتی: " + entry.memo),
        lines=reversed_lines,
    )
    reversal.reversal_of_id = entry.id
    db.flush()
    return post_entry(db, reversal.id, actor_id)


_MONTH_LAST_DAY = {
    1: 31,
    2: 31,
    3: 31,
    4: 31,
    5: 31,
    6: 31,
    7: 30,
    8: 30,
    9: 30,
    10: 30,
    11: 30,
    12: 29,
}


def list_entries(
    db: Session, company_id: int, *, period_year: int | None = None, period_month: int | None = None
) -> list[JournalEntry]:
    """List entries, optionally filtered by a Solar Hijri (year[, month]) period."""
    stmt = select(JournalEntry).where(JournalEntry.company_id == company_id)
    if period_year is not None:
        start = jalali_to_gregorian(period_year, 1, 1)
        end = jalali_to_gregorian(period_year, 12, _MONTH_LAST_DAY[12])
        if period_month is not None:
            start = jalali_to_gregorian(period_year, period_month, 1)
            end = jalali_to_gregorian(period_year, period_month, _MONTH_LAST_DAY[period_month])
        stmt = stmt.where(
            JournalEntry.entry_date >= start,
            JournalEntry.entry_date <= end,
        )
    stmt = stmt.order_by(JournalEntry.entry_date, JournalEntry.id)
    return list(db.scalars(stmt))


def entry_totals(entry: JournalEntry) -> tuple[int, int]:
    debit = sum(line.debit for line in entry.lines)
    credit = sum(line.credit for line in entry.lines)
    return debit, credit
