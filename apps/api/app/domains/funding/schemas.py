"""Funding schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.domains.funding.models import FundingType


class FundingEventCreate(BaseModel):
    funding_type: FundingType
    contact_id: int | None = None
    project_id: int | None = None
    event_date: dt.date
    amount: int = Field(gt=0)
    method: str = Field(default="cash", pattern="^(cash|bank|online)$")
    agreement_ref: str | None = Field(default=None, max_length=120)
    maturity_date: dt.date | None = None
    notes: str | None = Field(default=None, max_length=600)


class MappingUpdate(BaseModel):
    account_code: str = Field(min_length=1, max_length=20)


class FundingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str | None = None
    funding_type: FundingType
    contact_id: int | None = None
    contact_name: str = ""
    project_id: int | None = None
    event_date: dt.date
    amount: int
    method: str
    agreement_ref: str | None = None
    maturity_date: dt.date | None = None
    notes: str | None = None
    status: str
    journal_entry_id: int | None = None
    created_at: dt.datetime


class MappingOut(BaseModel):
    funding_type: FundingType
    account_code: str
