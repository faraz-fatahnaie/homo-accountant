"""Ledger API routes (thin; business logic lives in the service)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.identity.models import Role, User
from app.domains.ledger.models import Account, AccountingPeriod, JournalEntry
from app.domains.ledger.schemas import (
    AccountBalanceOut,
    AccountCreate,
    AccountOut,
    AccountUpdate,
    JournalEntryCreate,
    JournalEntryOut,
    JournalLineOut,
    PeriodOut,
)
from app.domains.ledger.service import (
    LedgerError,
    account_balances,
    close_period,
    create_account,
    create_draft_entry,
    list_accounts,
    list_entries,
    list_periods,
    post_entry,
    reopen_period,
    void_entry,
)

router = APIRouter(tags=["ledger"])

WRITERS = (Role.OWNER, Role.ACCOUNTANT)


def _ledger_error_handler(exc: LedgerError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


def _entry_out(entry: JournalEntry) -> JournalEntryOut:
    return JournalEntryOut(
        id=entry.id,
        entry_date=entry.entry_date,
        reference=entry.reference,
        memo=entry.memo,
        status=entry.status,
        reversal_of_id=entry.reversal_of_id,
        created_at=entry.created_at,
        posted_at=entry.posted_at,
        lines=[
            JournalLineOut(
                id=line.id,
                account_code=line.account.code,
                account_name=line.account.name,
                debit=line.debit,
                credit=line.credit,
            )
            for line in entry.lines
        ],
    )


# --------------------------------------------------------------------------
# Chart of Accounts
# --------------------------------------------------------------------------


@router.get("/accounts", response_model=list[AccountOut])
def accounts_list(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[Account]:
    company_id = _.company_id
    return list_accounts(db, company_id)


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def accounts_create(
    payload: AccountCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Account | JSONResponse:
    try:
        account = create_account(
            db,
            company_id=actor.company_id,
            code=payload.code,
            name=payload.name,
            atype=payload.type,
            parent_code=payload.parent_code,
        )
    except LedgerError as exc:
        return _ledger_error_handler(exc)
    db.commit()
    return account


@router.get("/accounts/balances", response_model=list[AccountBalanceOut])
def accounts_balances(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return account_balances(db, _.company_id)


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def accounts_update(
    account_id: int,
    payload: AccountUpdate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Account | JSONResponse:
    account = db.get(Account, account_id)
    if account is None or account.company_id != actor.company_id:
        return error_response(404, "not_found", "حساب یافت نشد")
    if account.is_system:
        return error_response(422, "account_system", "حساب سیستمی قابل تغییر نیست")
    if payload.name is not None:
        account.name = payload.name
    if payload.is_active is not None:
        account.is_active = payload.is_active
    db.commit()
    return account


# --------------------------------------------------------------------------
# Journal entries
# --------------------------------------------------------------------------


@router.get("/journal-entries", response_model=list[JournalEntryOut])
def entries_list(
    _: User = Depends(current_user),
    period_year: int | None = Query(default=None),
    period_month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> list[JournalEntryOut]:
    entries = list_entries(db, _.company_id, period_year=period_year, period_month=period_month)
    return [_entry_out(e) for e in entries]


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryOut)
def entry_detail(
    entry_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> JournalEntryOut | JSONResponse:
    entry = db.get(JournalEntry, entry_id)
    if entry is None or entry.company_id != user.company_id:
        return error_response(404, "not_found", "سند یافت نشد")
    return _entry_out(entry)


@router.post(
    "/journal-entries", response_model=JournalEntryOut, status_code=status.HTTP_201_CREATED
)
def entries_create(
    payload: JournalEntryCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> JournalEntryOut | JSONResponse:
    lines = [(ln.account_code, ln.debit, ln.credit) for ln in payload.lines]
    try:
        entry = create_draft_entry(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            entry_date=payload.entry_date,
            memo=payload.memo,
            lines=lines,
            idempotency_key=payload.idempotency_key,
        )
    except LedgerError as exc:
        return _ledger_error_handler(exc)
    db.commit()
    return _entry_out(entry)


@router.post("/journal-entries/{entry_id}/post", response_model=JournalEntryOut)
def entry_post(
    entry_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> JournalEntryOut | JSONResponse:
    try:
        entry = post_entry(db, entry_id, actor.id)
    except LedgerError as exc:
        db.rollback()
        return _ledger_error_handler(exc)
    db.commit()
    return _entry_out(entry)


@router.post("/journal-entries/{entry_id}/void", response_model=JournalEntryOut)
def entry_void(
    entry_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> JournalEntryOut | JSONResponse:
    try:
        reversal = void_entry(db, entry_id, actor.id)
    except LedgerError as exc:
        db.rollback()
        return _ledger_error_handler(exc)
    db.commit()
    return _entry_out(reversal)


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------


@router.get("/periods", response_model=list[PeriodOut])
def periods_list(
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AccountingPeriod]:
    return list_periods(db, _.company_id)


@router.post("/periods/{period_id}/close", response_model=PeriodOut)
def period_close(
    period_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> AccountingPeriod | JSONResponse:
    try:
        period = close_period(db, period_id, actor.id)
    except LedgerError as exc:
        db.rollback()
        return _ledger_error_handler(exc)
    db.commit()
    return period


@router.post("/periods/{period_id}/reopen", response_model=PeriodOut)
def period_reopen(
    period_id: int,
    actor: User = Depends(require_roles(Role.OWNER)),
    db: Session = Depends(get_db),
) -> AccountingPeriod | JSONResponse:
    try:
        period = reopen_period(db, period_id, actor.id)
    except LedgerError as exc:
        db.rollback()
        return _ledger_error_handler(exc)
    db.commit()
    return period
