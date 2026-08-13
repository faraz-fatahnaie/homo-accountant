"""Ledger Pydantic schemas (API contracts)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.money import rials
from app.domains.ledger.models import AccountType, JournalStatus, PeriodStatus


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    type: AccountType
    parent_code: str | None = Field(default=None, max_length=20)

    @field_validator("code")
    @classmethod
    def _code_no_spaces(cls, v: str) -> str:
        return v.strip()


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: AccountType
    parent_id: int | None = None
    is_active: bool
    is_system: bool


class JournalLineIn(BaseModel):
    account_code: str = Field(min_length=1, max_length=20)
    debit: int = Field(default=0, ge=0)
    credit: int = Field(default=0, ge=0)

    @field_validator("debit", "credit")
    @classmethod
    def _ints_only(cls, v: int) -> int:
        return rials(v)


class JournalEntryCreate(BaseModel):
    entry_date: dt.date
    memo: str = Field(min_length=1, max_length=500)
    lines: list[JournalLineIn] = Field(min_length=1, max_length=500)
    idempotency_key: str | None = Field(default=None, max_length=64)


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_code: str
    account_name: str
    debit: int
    credit: int


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: dt.date
    reference: str | None
    memo: str
    status: JournalStatus
    reversal_of_id: int | None
    created_at: dt.datetime
    posted_at: dt.datetime | None
    lines: list[JournalLineOut]


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    month: int
    status: PeriodStatus
    closed_at: dt.datetime | None
    reopened_at: dt.datetime | None
