"""Bills Pydantic schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.bills.models import BillStatus


class BillCreate(BaseModel):
    vendor_id: int
    project_id: int | None = None
    account_code: str = Field(min_length=1, max_length=20)
    issue_date: dt.date
    due_date: dt.date
    bill_number: str | None = Field(default=None, max_length=80)
    memo: str = Field(min_length=1, max_length=400)
    total: int = Field(gt=0)

    @model_validator(mode="after")
    def _dates(self) -> BillCreate:
        if self.due_date < self.issue_date:
            raise ValueError("سررسید نمی‌تواند قبل از تاریخ فاکتور باشد")
        return self


class PaymentIn(BaseModel):
    amount: int = Field(gt=0)
    paid_at: dt.date
    method: str = Field(default="cash", pattern="^(cash|bank|online)$")
    reference: str | None = Field(default=None, max_length=80)


class BillPaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: int
    paid_at: dt.date
    method: str
    reference: str | None = None
    journal_entry_id: int | None = None
    created_at: dt.datetime


class BillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str | None = None
    vendor_id: int
    vendor_name: str = ""
    project_id: int | None = None
    account_code: str = ""
    account_name: str = ""
    issue_date: dt.date
    due_date: dt.date
    bill_number: str | None = None
    status: BillStatus
    memo: str
    total: int
    paid_total: int = 0
    balance: int = 0
    is_overdue: bool = False
    journal_entry_id: int | None = None
    created_at: dt.datetime
    payments: list[BillPaymentOut] = []
