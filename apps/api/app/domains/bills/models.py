"""Bills (payables): bill + bill payments."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class BillStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    VOID = "void"


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str | None] = mapped_column(String(30), index=True)
    vendor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    bill_number: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[BillStatus] = mapped_column(
        Enum(BillStatus, name="bill_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=BillStatus.DRAFT,
        index=True,
    )
    memo: Mapped[str] = mapped_column(String(400), nullable=False)
    total: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    journal_entry_id: Mapped[int | None] = mapped_column(Integer)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    payments: Mapped[list[BillPayment]] = relationship(
        back_populates="bill", cascade="all, delete-orphan", order_by="BillPayment.id"
    )


class BillPayment(Base):
    __tablename__ = "bill_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(
        ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paid_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")
    reference: Mapped[str | None] = mapped_column(String(80))
    journal_entry_id: Mapped[int | None] = mapped_column(Integer)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bill: Mapped[Bill] = relationship(back_populates="payments")
