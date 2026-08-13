"""Invoices Pydantic schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.invoices.models import InvoiceStatus


class InvoiceItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: int = Field(default=1, ge=1)
    unit_price: int = Field(ge=0)
    discount: int = Field(default=0, ge=0)


class InvoiceCreate(BaseModel):
    customer_id: int
    project_id: int | None = None
    issue_date: dt.date
    due_date: dt.date
    items: list[InvoiceItemIn] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=600)
    payment_instructions: str | None = Field(default=None, max_length=400)

    @model_validator(mode="after")
    def _dates(self) -> InvoiceCreate:
        if self.due_date < self.issue_date:
            raise ValueError("سررسید نمیتواند قبل از تاریخ صدور باشد")
        return self


class InvoiceItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    quantity: int
    unit_price: int
    discount: int
    line_total: int


class InvoicePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    paid_at: dt.date
    method: str
    reference: str | None = None
    journal_entry_id: int | None = None
    created_at: dt.datetime


class PaymentIn(BaseModel):
    amount: int = Field(gt=0)
    paid_at: dt.date
    method: str = Field(default="cash", pattern="^(cash|bank|online)$")
    reference: str | None = Field(default=None, max_length=80)


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str | None = None
    customer_id: int
    customer_name: str = ""
    project_id: int | None = None
    issue_date: dt.date
    due_date: dt.date
    status: InvoiceStatus
    notes: str | None = None
    payment_instructions: str | None = None
    total: int
    paid_total: int = 0
    balance: int = 0
    is_overdue: bool = False
    journal_entry_id: int | None = None
    created_at: dt.datetime
    items: list[InvoiceItemOut] = []
    payments: list[InvoicePaymentOut] = []
