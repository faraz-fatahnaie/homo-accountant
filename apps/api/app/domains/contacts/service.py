"""Contacts service."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.contacts.models import Contact

logger = logging.getLogger(__name__)


class ContactError(Exception):
    def __init__(self, message: str, code: str = "contact_error", status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def list_contacts(db: Session, company_id: int, *, active_only: bool = False) -> list[Contact]:
    stmt = select(Contact).where(Contact.company_id == company_id)
    if active_only:
        stmt = stmt.where(Contact.is_active.is_(True))
    return list(db.scalars(stmt.order_by(Contact.name)))


def get_contact(db: Session, company_id: int, contact_id: int) -> Contact | None:
    contact = db.get(Contact, contact_id)
    if contact is None or contact.company_id != company_id:
        return None
    return contact


def create_contact(
    db: Session,
    *,
    company_id: int,
    name: str,
    roles: list[str] | None,
    phone: str | None,
    email: str | None,
    national_id: str | None,
    address: str | None,
    payment_terms_days: int,
    notes: str | None,
) -> Contact:
    contact = Contact(
        company_id=company_id,
        name=name.strip(),
        roles=roles or [],
        phone=phone,
        email=email.lower() if email else None,
        national_id=national_id,
        address=address,
        payment_terms_days=payment_terms_days,
        notes=notes,
    )
    db.add(contact)
    db.flush()
    logger.info("contact created", extra={"contact_id": contact.id, "contact_name": contact.name})
    return contact


def update_contact(db: Session, contact: Contact, **changes: object) -> Contact:
    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"]).lower()
    for key, value in changes.items():
        if value is not None:
            setattr(contact, key, value)
    db.flush()
    return contact
