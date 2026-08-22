"""Funding API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.contacts.service import get_contact
from app.domains.funding.models import FundingEvent, FundingType
from app.domains.funding.schemas import (
    FundingEventCreate,
    FundingEventOut,
    MappingOut,
    MappingUpdate,
)
from app.domains.funding.service import (
    FundingError,
    create_funding_event,
    get_funding_event,
    list_funding_events,
    list_mappings,
    upsert_mapping,
)
from app.domains.identity.models import Role, User

router = APIRouter(tags=["funding"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)


def _to_out(db: Session, event: FundingEvent) -> FundingEventOut:
    contact = get_contact(db, event.company_id, event.contact_id) if event.contact_id else None
    return FundingEventOut(
        id=event.id,
        number=event.number,
        funding_type=event.funding_type,
        contact_id=event.contact_id,
        contact_name=contact.name if contact else "",
        project_id=event.project_id,
        event_date=event.event_date,
        amount=event.amount,
        method=event.method,
        agreement_ref=event.agreement_ref,
        maturity_date=event.maturity_date,
        notes=event.notes,
        status=event.status,
        journal_entry_id=event.journal_entry_id,
        created_at=event.created_at,
    )


def _handle(exc: FundingError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@router.get("/funding", response_model=list[FundingEventOut])
def funding_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[FundingEventOut]:
    return [_to_out(db, e) for e in list_funding_events(db, user.company_id)]


@router.post("/funding", response_model=FundingEventOut, status_code=status.HTTP_201_CREATED)
def funding_create(
    payload: FundingEventCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> FundingEventOut | JSONResponse:
    if payload.contact_id:
        contact = get_contact(db, actor.company_id, payload.contact_id)
        if contact is None:
            return error_response(404, "not_found", "طرف‌حساب یافت نشد")
    try:
        event = create_funding_event(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            funding_type=payload.funding_type,
            contact_id=payload.contact_id,
            project_id=payload.project_id,
            event_date=payload.event_date,
            amount=payload.amount,
            method=payload.method,
            agreement_ref=payload.agreement_ref,
            maturity_date=payload.maturity_date,
            notes=payload.notes,
        )
    except FundingError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, event)


@router.get("/funding/mappings", response_model=list[MappingOut])
def funding_mappings(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[MappingOut]:
    return [
        MappingOut(funding_type=m.funding_type, account_code=m.account_code)
        for m in list_mappings(db, user.company_id)
    ]


@router.put("/funding/mappings/{funding_type}", response_model=MappingOut)
def funding_mapping_update(
    funding_type: FundingType,
    payload: MappingUpdate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> MappingOut | JSONResponse:
    try:
        mapping = upsert_mapping(db, actor.company_id, funding_type, payload.account_code)
    except FundingError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return MappingOut(funding_type=mapping.funding_type, account_code=mapping.account_code)


@router.get("/funding/{event_id}", response_model=FundingEventOut)
def funding_detail(
    event_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> FundingEventOut | JSONResponse:
    event = get_funding_event(db, user.company_id, event_id)
    if event is None:
        return error_response(404, "not_found", "رویداد تأمین مالی یافت نشد")
    return _to_out(db, event)
