"""Funding service.

Each funding event posts through an explicit, configurable account mapping:
    Dr 101/102 (cash/bank)   amount
    Cr <mapped account>      amount
Default mappings: investment→301 سرمایه مالک, loan→205 وام دریافتی,
grant→403 درآمد کمک بلاعوض, revenue→401 درآمد فروش.
Loans and owner investment are NEVER booked as revenue.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jalali import entry_period
from app.domains.funding.models import FundingAccountMapping, FundingEvent, FundingType
from app.domains.ledger.service import (
    create_draft_entry,
    get_account,
    next_reference,
    post_entry,
)

logger = logging.getLogger(__name__)


class FundingError(Exception):
    def __init__(self, message: str, code: str = "funding_error", status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


DEFAULT_MAPPINGS: dict[FundingType, str] = {
    FundingType.INVESTMENT: "301",
    FundingType.LOAN: "205",
    FundingType.GRANT: "403",
    FundingType.REVENUE: "401",
}


def get_mapping(
    db: Session, company_id: int, funding_type: FundingType
) -> FundingAccountMapping | None:
    return db.scalar(
        select(FundingAccountMapping).where(
            FundingAccountMapping.company_id == company_id,
            FundingAccountMapping.funding_type == funding_type,
        )
    )


# account type for each default mapping code (used to create missing accounts)
_MAPPED_ACCOUNT_TYPES: dict[str, str] = {
    "301": "equity",
    "205": "liability",
    "403": "revenue",
    "401": "revenue",
}
_MAPPED_ACCOUNT_NAMES: dict[str, str] = {
    "301": "سرمایه مالک",
    "205": "وام دریافتی",
    "403": "درآمد کمک بلاعوض",
    "401": "درآمد فروش",
}


def ensure_default_mappings(db: Session, company_id: int) -> int:
    """Create the 4 default account mappings if absent (idempotent), ensuring
    the mapped accounts exist in the chart of accounts."""
    from app.domains.ledger.models import Account, AccountType

    created = 0
    existing = {m.funding_type for m in list_mappings(db, company_id)}
    for funding_type, code in DEFAULT_MAPPINGS.items():
        if funding_type not in existing:
            # ensure the mapped account exists
            account = get_account(db, company_id, code)
            if account is None:
                db.add(
                    Account(
                        company_id=company_id,
                        code=code,
                        name=_MAPPED_ACCOUNT_NAMES[code],
                        type=AccountType(_MAPPED_ACCOUNT_TYPES[code]),
                        is_system=True,
                    )
                )
            db.add(
                FundingAccountMapping(
                    company_id=company_id, funding_type=funding_type, account_code=code
                )
            )
            created += 1
    if created:
        db.flush()
    return created


def list_mappings(db: Session, company_id: int) -> list[FundingAccountMapping]:
    return list(
        db.scalars(
            select(FundingAccountMapping).where(FundingAccountMapping.company_id == company_id)
        )
    )


def upsert_mapping(
    db: Session, company_id: int, funding_type: FundingType, account_code: str
) -> FundingAccountMapping:
    account = get_account(db, company_id, account_code)
    if account is None:
        raise FundingError(f"حساب با کد {account_code} یافت نشد", code="account_missing")
    mapping = get_mapping(db, company_id, funding_type)
    if mapping is None:
        mapping = FundingAccountMapping(
            company_id=company_id, funding_type=funding_type, account_code=account_code
        )
        db.add(mapping)
    else:
        mapping.account_code = account_code
    db.flush()
    logger.info(
        "funding mapping set", extra={"funding_type": funding_type.value, "code": account_code}
    )
    return mapping


def _resolve_account_code(db: Session, company_id: int, funding_type: FundingType) -> str:
    mapping = get_mapping(db, company_id, funding_type)
    if mapping is not None:
        return mapping.account_code
    return DEFAULT_MAPPINGS[funding_type]


def create_funding_event(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    funding_type: FundingType,
    contact_id: int | None,
    project_id: int | None,
    event_date: dt.date,
    amount: int,
    method: str,
    agreement_ref: str | None,
    maturity_date: dt.date | None,
    notes: str | None,
) -> FundingEvent:
    if funding_type == FundingType.LOAN and maturity_date is None:
        raise FundingError("برای وام، تاریخ سررسید الزامی است", code="loan_maturity_required")
    if (
        funding_type == FundingType.LOAN
        and maturity_date is not None
        and maturity_date < event_date
    ):
        raise FundingError(
            "سررسید وام نمیتواند قبل از تاریخ دریافت باشد", code="loan_maturity_invalid"
        )
    account_code = _resolve_account_code(db, company_id, funding_type)
    account = get_account(db, company_id, account_code)
    if account is None or not account.is_active:
        raise FundingError(
            f"حساب نگاشت {account_code} برای {funding_type.value} موجود نیست",
            code="mapping_account_missing",
        )
    cash_account = "101" if method == "cash" else "102"
    entry = create_draft_entry(
        db,
        company_id=company_id,
        actor_id=actor_id,
        entry_date=event_date,
        memo=f"{funding_type.value}: {agreement_ref or 'تأمین مالی'}",
        lines=[(cash_account, amount, 0), (account_code, 0, amount)],
        idempotency_key=None,
    )
    posted = post_entry(db, entry.id, actor_id)
    year, month = entry_period(event_date)
    event = FundingEvent(
        company_id=company_id,
        funding_type=funding_type,
        contact_id=contact_id,
        project_id=project_id,
        event_date=event_date,
        amount=amount,
        method=method,
        agreement_ref=agreement_ref,
        maturity_date=maturity_date,
        notes=notes,
        journal_entry_id=posted.id,
        created_by_id=actor_id,
    )
    db.add(event)
    db.flush()
    event.number = next_reference(db, company_id, year, month, "FDG")
    db.flush()
    logger.info(
        "funding event created",
        extra={
            "event_id": event.id,
            "type": funding_type.value,
            "amount": amount,
            "entry": posted.id,
        },
    )
    return event


def list_funding_events(db: Session, company_id: int) -> list[FundingEvent]:
    return list(
        db.scalars(
            select(FundingEvent)
            .where(FundingEvent.company_id == company_id)
            .order_by(FundingEvent.event_date.desc(), FundingEvent.id.desc())
        )
    )


def get_funding_event(db: Session, company_id: int, event_id: int) -> FundingEvent | None:
    event = db.get(FundingEvent, event_id)
    if event is None or event.company_id != company_id:
        return None
    return event


def loan_balance(db: Session, company_id: int) -> int:
    """Sum of posted loan amounts (outstanding principal tracked via repayment events
    is a later refinement; MVP records the liability balance)."""
    total = db.scalar(
        select(FundingEvent.amount).where(
            FundingEvent.company_id == company_id,
            FundingEvent.funding_type == FundingType.LOAN,
        )
    )
    return int(total) if total else 0
