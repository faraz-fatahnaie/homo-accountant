"""Bills service: lifecycle + posting rules.

Post:    Dr <expense/account>  total   /   Cr 204 حساب‌های پرداختنی  total
Payment: Dr 204 پرداختنی         amount /   Cr 101/102 (cash/bank)   amount
Void:    reversal of the post entry (only when nothing was paid).
All flows are single-transaction and reuse the ledger posting service.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.jalali import entry_period
from app.domains.bills.models import Bill, BillPayment, BillStatus
from app.domains.ledger.service import (
    create_draft_entry,
    get_account,
    next_reference,
    post_entry,
    void_entry,
)

logger = logging.getLogger(__name__)

PAYABLE_ACCOUNT = "204"


class BillError(AppError):
    def __init__(self, message: str, code: str = "bill_error", status_code: int = 422) -> None:
        super().__init__(message, code=code, status_code=status_code)


def create_bill(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    vendor_id: int,
    project_id: int | None,
    account_code: str,
    issue_date: dt.date,
    due_date: dt.date,
    bill_number: str | None,
    memo: str,
    total: int,
) -> Bill:
    if due_date < issue_date:
        raise BillError("سررسید نمی‌تواند قبل از تاریخ فاکتور باشد", code="bill_dates_invalid")
    if project_id is not None:
        from app.domains.projects.service import get_project

        if get_project(db, company_id, project_id) is None:
            raise BillError("پروژه یافت نشد", code="project_missing", status_code=404)
    account = get_account(db, company_id, account_code)
    if account is None:
        raise BillError(f"حساب با کد {account_code} یافت نشد", code="account_missing")
    if not account.is_active:
        raise BillError(f"حساب {account_code} غیرفعال است", code="account_inactive")
    bill = Bill(
        company_id=company_id,
        vendor_id=vendor_id,
        project_id=project_id,
        account_id=account.id,
        issue_date=issue_date,
        due_date=due_date,
        bill_number=bill_number,
        memo=memo.strip(),
        total=total,
        status=BillStatus.DRAFT,
        created_by_id=actor_id,
    )
    db.add(bill)
    db.flush()
    logger.info("bill draft created", extra={"bill_id": bill.id, "by": actor_id})
    return bill


def _paid_total(db: Session, bill_id: int) -> int:
    paid = db.scalar(
        select(func.coalesce(func.sum(BillPayment.amount), 0)).where(BillPayment.bill_id == bill_id)
    )
    return int(paid or 0)


def post_bill(db: Session, company_id: int, bill_id: int, actor_id: int) -> Bill:
    bill = db.scalar(select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id))
    if bill is None:
        raise BillError("فاکتور خرید یافت نشد", code="bill_missing", status_code=404)
    if bill.status == BillStatus.VOID:
        raise BillError("فاکتور خرید باطل شده است", code="bill_voided")
    if bill.journal_entry_id is not None:
        raise BillError("فاکتور خرید از قبل ثبت شده است", code="bill_already_posted")
    from app.domains.ledger.models import Account

    account = db.get(Account, bill.account_id)
    if account is None:
        raise BillError("حساب مرتبط یافت نشد", code="account_missing")
    entry = create_draft_entry(
        db,
        company_id=bill.company_id,
        actor_id=actor_id,
        entry_date=bill.issue_date,
        memo=f"فاکتور خرید: {bill.memo}",
        lines=[(account.code, bill.total, 0), (PAYABLE_ACCOUNT, 0, bill.total)],
        idempotency_key=None,
    )
    posted = post_entry(db, company_id, entry.id, actor_id)
    year, month = entry_period(bill.issue_date)
    bill.number = next_reference(db, bill.company_id, year, month, "BIL")
    bill.journal_entry_id = posted.id
    bill.status = BillStatus.OPEN
    db.flush()
    logger.info(
        "bill posted", extra={"bill_id": bill.id, "number": bill.number, "entry": posted.id}
    )
    return bill


def record_payment(
    db: Session,
    *,
    company_id: int,
    bill_id: int,
    actor_id: int,
    amount: int,
    paid_at: dt.date,
    method: str,
    reference: str | None,
) -> BillPayment:
    bill = db.scalar(select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id))
    if bill is None:
        raise BillError("فاکتور خرید یافت نشد", code="bill_missing", status_code=404)
    if bill.status in (BillStatus.DRAFT, BillStatus.VOID):
        raise BillError("فقط فاکتور خرید ثبت‌شده را می‌توان پرداخت کرد", code="bill_not_posted")
    if bill.journal_entry_id is None:
        raise BillError("فاکتور خرید هنوز ثبت نشده است", code="bill_not_posted")
    paid = _paid_total(db, bill.id)
    if paid + amount > bill.total:
        raise BillError("مبلغ پرداختی بیش از مانده است", code="bill_overpayment")
    cash_account = "101" if method == "cash" else "102"
    entry = create_draft_entry(
        db,
        company_id=bill.company_id,
        actor_id=actor_id,
        entry_date=paid_at,
        memo=f"پرداخت فاکتور خرید {bill.number or bill.id}",
        lines=[(PAYABLE_ACCOUNT, amount, 0), (cash_account, 0, amount)],
        idempotency_key=None,
    )
    posted = post_entry(db, company_id, entry.id, actor_id)
    payment = BillPayment(
        bill_id=bill.id,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        journal_entry_id=posted.id,
        created_by_id=actor_id,
    )
    db.add(payment)
    db.flush()
    paid = _paid_total(db, bill.id)
    if paid >= bill.total:
        bill.status = BillStatus.PAID
    else:
        bill.status = BillStatus.PARTIALLY_PAID
    db.flush()
    logger.info(
        "bill payment recorded", extra={"bill_id": bill.id, "amount": amount, "entry": posted.id}
    )
    return payment


def void_bill(db: Session, company_id: int, bill_id: int, actor_id: int) -> Bill:
    bill = db.scalar(select(Bill).where(Bill.id == bill_id, Bill.company_id == company_id))
    if bill is None:
        raise BillError("فاکتور خرید یافت نشد", code="bill_missing", status_code=404)
    if bill.status == BillStatus.VOID:
        raise BillError("فاکتور خرید از قبل باطل شده است", code="bill_already_voided")
    if bill.journal_entry_id is None:
        bill.status = BillStatus.VOID
        db.flush()
        return bill
    if _paid_total(db, bill.id) > 0:
        raise BillError(
            "فاکتور خریدی که پرداخت داشته را نمی‌توان باطل کرد",
            code="bill_has_payments",
        )
    void_entry(
        db,
        company_id,
        bill.journal_entry_id,
        actor_id,
        memo=f"ابطال فاکتور خرید {bill.number or bill.id}",
    )
    bill.status = BillStatus.VOID
    db.flush()
    logger.info("bill voided", extra={"bill_id": bill.id})
    return bill


def list_bills(db: Session, company_id: int) -> list[Bill]:
    return list(
        db.scalars(
            select(Bill)
            .where(Bill.company_id == company_id)
            .order_by(Bill.issue_date.desc(), Bill.id.desc())
        )
    )


def get_bill(db: Session, company_id: int, bill_id: int) -> Bill | None:
    bill = db.get(Bill, bill_id)
    if bill is None or bill.company_id != company_id:
        return None
    return bill


def bill_metrics(db: Session, bill: Bill, today: dt.date | None = None) -> tuple[int, int, bool]:
    paid = _paid_total(db, bill.id)
    balance = bill.total - paid
    t = today or dt.date.today()
    overdue = bill.status in (BillStatus.OPEN, BillStatus.PARTIALLY_PAID) and bill.due_date < t
    return paid, balance, overdue
