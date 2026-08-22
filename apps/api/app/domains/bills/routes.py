"""Bills API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.bills.models import Bill
from app.domains.bills.schemas import (
    BillCreate,
    BillOut,
    BillPaymentOut,
    PaymentIn,
)
from app.domains.bills.service import (
    BillError,
    bill_metrics,
    create_bill,
    get_bill,
    list_bills,
    post_bill,
    record_payment,
    void_bill,
)
from app.domains.contacts.service import get_contact
from app.domains.identity.models import Role, User
from app.domains.ledger.models import Account

router = APIRouter(tags=["bills"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)


def _to_out(db: Session, bill: Bill) -> BillOut:
    paid, balance, overdue = bill_metrics(db, bill)
    vendor = get_contact(db, bill.company_id, bill.vendor_id)
    account = db.get(Account, bill.account_id)
    return BillOut(
        id=bill.id,
        number=bill.number,
        vendor_id=bill.vendor_id,
        vendor_name=vendor.name if vendor else "—",
        project_id=bill.project_id,
        account_code=account.code if account else "?",
        account_name=account.name if account else "?",
        issue_date=bill.issue_date,
        due_date=bill.due_date,
        bill_number=bill.bill_number,
        status=bill.status,
        memo=bill.memo,
        total=bill.total,
        paid_total=paid,
        balance=balance,
        is_overdue=overdue,
        journal_entry_id=bill.journal_entry_id,
        created_at=bill.created_at,
        payments=list(bill.payments),
    )


def _handle(exc: BillError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@router.get("/bills", response_model=list[BillOut])
def bills_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[BillOut]:
    return [_to_out(db, b) for b in list_bills(db, user.company_id)]


@router.post("/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED)
def bills_create(
    payload: BillCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> BillOut | JSONResponse:
    vendor = get_contact(db, actor.company_id, payload.vendor_id)
    if vendor is None:
        return error_response(404, "not_found", "تأمین‌کننده یافت نشد")
    try:
        bill = create_bill(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            vendor_id=payload.vendor_id,
            project_id=payload.project_id,
            account_code=payload.account_code,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            bill_number=payload.bill_number,
            memo=payload.memo,
            total=payload.total,
        )
    except BillError as exc:
        return _handle(exc)
    db.commit()
    return _to_out(db, bill)


@router.get("/bills/{bill_id}", response_model=BillOut)
def bills_detail(
    bill_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> BillOut | JSONResponse:
    bill = get_bill(db, user.company_id, bill_id)
    if bill is None:
        return error_response(404, "not_found", "فاکتور خرید یافت نشد")
    return _to_out(db, bill)


@router.post("/bills/{bill_id}/post", response_model=BillOut)
def bills_post(
    bill_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> BillOut | JSONResponse:
    try:
        bill = post_bill(db, actor.company_id, bill_id, actor.id)
    except BillError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, bill)


@router.post(
    "/bills/{bill_id}/payments", response_model=BillPaymentOut, status_code=status.HTTP_201_CREATED
)
def bills_pay(
    bill_id: int,
    payload: PaymentIn,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> BillPaymentOut | JSONResponse:
    try:
        payment = record_payment(
            db,
            company_id=actor.company_id,
            bill_id=bill_id,
            actor_id=actor.id,
            amount=payload.amount,
            paid_at=payload.paid_at,
            method=payload.method,
            reference=payload.reference,
        )
    except BillError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return BillPaymentOut.model_validate(payment)


@router.post("/bills/{bill_id}/void", response_model=BillOut)
def bills_void(
    bill_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> BillOut | JSONResponse:
    try:
        bill = void_bill(db, actor.company_id, bill_id, actor.id)
    except BillError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, bill)
