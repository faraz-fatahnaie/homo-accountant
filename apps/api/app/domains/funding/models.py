"""Funding events (investment / loan / grant / revenue)."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FundingType(StrEnum):
    INVESTMENT = "investment"
    LOAN = "loan"
    GRANT = "grant"
    REVENUE = "revenue"


class FundingAccountMapping(Base):
    __tablename__ = "funding_account_mappings"
    __table_args__ = (
        UniqueConstraint("company_id", "funding_type", name="uq_funding_map_company_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False)
    funding_type: Mapped[FundingType] = mapped_column(
        Enum(FundingType, name="funding_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    account_code: Mapped[str] = mapped_column(String(20), nullable=False)


class FundingEvent(Base):
    __tablename__ = "funding_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str | None] = mapped_column(String(30), index=True)
    funding_type: Mapped[FundingType] = mapped_column(
        Enum(FundingType, name="funding_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[int | None] = mapped_column(Integer)
    event_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")
    agreement_ref: Mapped[str | None] = mapped_column(String(120))
    maturity_date: Mapped[dt.date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")
    journal_entry_id: Mapped[int | None] = mapped_column(Integer)
    created_by_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
