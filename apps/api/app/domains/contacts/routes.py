"""Contacts API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.contacts.models import Contact
from app.domains.contacts.schemas import ContactCreate, ContactOut, ContactUpdate
from app.domains.contacts.service import (
    create_contact,
    get_contact,
    list_contacts,
    update_contact,
)
from app.domains.identity.models import Role, User

router = APIRouter(tags=["contacts"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)


@router.get("/contacts", response_model=list[ContactOut])
def contacts_list(
    user: User = Depends(current_user),
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[Contact]:
    return list_contacts(db, user.company_id, active_only=active_only)


@router.post("/contacts", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def contacts_create(
    payload: ContactCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Contact:
    contact = create_contact(
        db,
        company_id=actor.company_id,
        name=payload.name,
        roles=payload.roles,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        national_id=payload.national_id,
        address=payload.address,
        payment_terms_days=payload.payment_terms_days,
        notes=payload.notes,
    )
    db.commit()
    return contact


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
def contacts_update(
    contact_id: int,
    payload: ContactUpdate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Contact | JSONResponse:
    contact = get_contact(db, actor.company_id, contact_id)
    if contact is None:
        return error_response(404, "not_found", "طرف‌حساب یافت نشد")
    changes = payload.model_dump(exclude_unset=True)
    if "roles" in changes and changes["roles"] is not None:
        try:
            changes["roles"] = ContactCreate._valid_roles(changes["roles"])
        except ValueError as exc:
            return error_response(422, "invalid_roles", str(exc))
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"])
    update_contact(db, contact, **changes)
    db.commit()
    return contact
