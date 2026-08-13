"""Expenses domain: expense records + attachments (receipts)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PaymentMethod(StrEnum):
    CASH = "cash"
    BANK = "bank"
    ONLINE = "online"


class ExpenseStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    VOIDED = "voided"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str | None] = mapped_column(String(30), index=True)
    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    contact_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PaymentMethod.CASH,
    )
    reference: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(400), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(600))
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, name="expense_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ExpenseStatus.DRAFT,
        index=True,
    )
    journal_entry_id: Mapped[int | None] = mapped_column(Integer)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    attachments: Mapped[list[Attachment]] = relationship(
        primaryjoin=(
            "and_(Attachment.owner_type=='expense', foreign(Attachment.owner_id)==Expense.id)"
        ),
        viewonly=True,
        order_by="Attachment.id",
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
