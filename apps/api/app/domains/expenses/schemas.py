"""Expenses Pydantic schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from app.domains.expenses.models import ExpenseStatus, PaymentMethod


class ExpenseCreate(BaseModel):
    entry_date: dt.date
    contact_id: int | None = None
    project_id: int | None = None
    account_code: str = Field(min_length=1, max_length=20)
    amount: int = Field(gt=0)
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference: str | None = Field(default=None, max_length=80)
    description: str = Field(min_length=1, max_length=400)
    notes: str | None = Field(default=None, max_length=600)
    idempotency_key: str | None = Field(default=None, max_length=64)


class ExpenseUpdate(BaseModel):
    contact_id: int | None = None
    project_id: int | None = None
    reference: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, min_length=1, max_length=400)
    notes: str | None = Field(default=None, max_length=600)


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size_bytes: int
    created_at: dt.datetime


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str | None = None
    entry_date: dt.date
    contact_id: int | None = None
    project_id: int | None = None
    account_code: str
    account_name: str
    amount: int
    payment_method: PaymentMethod
    reference: str | None = None
    description: str
    notes: str | None = None
    status: ExpenseStatus
    journal_entry_id: int | None = None
    created_at: dt.datetime
    posted_at: dt.datetime | None = None
    attachments: list[AttachmentOut] = []
