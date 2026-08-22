"""Contacts Pydantic schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domains.contacts.models import CONTACT_ROLES


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    roles: list[str] = Field(default_factory=list)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    national_id: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=600)

    @field_validator("roles")
    @classmethod
    def _valid_roles(cls, v: list[str]) -> list[str]:
        invalid = [r for r in v if r not in CONTACT_ROLES]
        if invalid:
            raise ValueError(f"نقش‌های نامعتبر: {', '.join(invalid)}")
        return list(dict.fromkeys(v))  # de-duplicate, preserve order


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    roles: list[str] | None = None
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    national_id: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=600)
    is_active: bool | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    roles: list[str]
    phone: str | None = None
    email: str | None = None
    national_id: str | None = None
    address: str | None = None
    payment_terms_days: int
    notes: str | None = None
    is_active: bool
    created_at: dt.datetime
