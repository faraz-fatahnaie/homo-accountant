"""Ledger domain: chart of accounts, journal entries, periods, sequences."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JournalStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("reversal_of_id", name="uq_journal_entries_reversal_of"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    entry_date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    memo: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[JournalStatus] = mapped_column(
        Enum(
            JournalStatus,
            name="journal_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=JournalStatus.DRAFT,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    posted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    posted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list[JournalLine]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    reversal_of: Mapped[JournalEntry | None] = relationship(
        remote_side=[id], foreign_keys=[reversal_of_id]
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="ck_line_single_side",
        ),
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_line_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    debit: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credit: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()


class PeriodStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "month", name="uq_periods_company_ym"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(
            PeriodStatus,
            name="period_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PeriodStatus.OPEN,
    )
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reopened_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    events: Mapped[list[PeriodEvent]] = relationship(
        back_populates="period", cascade="all, delete-orphan"
    )


class PeriodAction(StrEnum):
    CLOSE = "close"
    REOPEN = "reopen"


class PeriodEvent(Base):
    """Recorded close/reopen events (accountability trail for periods)."""

    __tablename__ = "period_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[PeriodAction] = mapped_column(
        Enum(
            PeriodAction,
            name="period_action",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    period: Mapped[AccountingPeriod] = relationship(back_populates="events")


class PeriodSequence(Base):
    """Per-period counters used to generate safe sequential references."""

    __tablename__ = "period_sequences"
    __table_args__ = (
        UniqueConstraint("company_id", "year", "month", "kind", name="uq_seq_company_ym_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, default="J")
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


Index("ix_journal_lines_entry_account", JournalLine.entry_id, JournalLine.account_id)
