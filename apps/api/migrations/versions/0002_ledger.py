"""Ledger schema: accounts, journal entries/lines, periods, sequences."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_ledger"
down_revision = "0001_identity"
branch_labels = None
depends_on = None

# create_type=False: DDL controlled explicitly (see 0001 for rationale).
account_type = postgresql.ENUM("asset", "liability", "equity", "revenue", "expense", name="account_type", create_type=False)
journal_status = postgresql.ENUM("draft", "posted", name="journal_status", create_type=False)
period_status = postgresql.ENUM("open", "closed", name="period_status", create_type=False)
period_action = postgresql.ENUM("close", "reopen", name="period_action", create_type=False)


def upgrade() -> None:
    account_type.create(op.get_bind(), checkfirst=True)
    journal_status.create(op.get_bind(), checkfirst=True)
    period_status.create(op.get_bind(), checkfirst=True)
    period_action.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", account_type, nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "code", name="uq_accounts_company_code"),
    )
    op.create_index("ix_accounts_company_id", "accounts", ["company_id"])
    op.create_index("ix_accounts_type", "accounts", ["type"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(30), nullable=True),
        sa.Column("memo", sa.String(500), nullable=False),
        sa.Column("status", journal_status, nullable=False, server_default="draft"),
        sa.Column("idempotency_key", sa.String(64), nullable=True, unique=True),
        sa.Column("reversal_of_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_journal_entries_company_id", "journal_entries", ["company_id"])
    op.create_index("ix_journal_entries_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entries_reference", "journal_entries", ["reference"])
    op.create_index("ix_journal_entries_status", "journal_entries", ["status"])

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("credit", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="ck_line_single_side",
        ),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_line_non_negative"),
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_lines_account_id", "journal_lines", ["account_id"])
    op.create_index("ix_journal_lines_entry_account", "journal_lines", ["entry_id", "account_id"])

    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("status", period_status, nullable=False, server_default="open"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("company_id", "year", "month", name="uq_periods_company_ym"),
    )
    op.create_index("ix_accounting_periods_company_id", "accounting_periods", ["company_id"])

    op.create_table(
        "period_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", period_action, nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_period_events_period_id", "period_events", ["period_id"])

    op.create_table(
        "period_sequences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("company_id", "year", "month", name="uq_seq_company_ym"),
    )
    op.create_index("ix_period_sequences_company_id", "period_sequences", ["company_id"])


def downgrade() -> None:
    op.drop_table("period_sequences")
    op.drop_table("period_events")
    op.drop_table("accounting_periods")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
    period_action.drop(op.get_bind(), checkfirst=True)
    period_status.drop(op.get_bind(), checkfirst=True)
    journal_status.drop(op.get_bind(), checkfirst=True)
    account_type.drop(op.get_bind(), checkfirst=True)
