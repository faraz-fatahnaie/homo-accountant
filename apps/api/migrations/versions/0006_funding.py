"""Funding: events + account mappings."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_funding"
down_revision = "0005_bills"
branch_labels = None
depends_on = None

funding_type = postgresql.ENUM(
    "investment", "loan", "grant", "revenue", name="funding_type", create_type=False
)


def upgrade() -> None:
    funding_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "funding_account_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("funding_type", funding_type, nullable=False),
        sa.Column("account_code", sa.String(20), nullable=False),
        sa.UniqueConstraint("company_id", "funding_type", name="uq_funding_map_company_type"),
    )

    op.create_table(
        "funding_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(30), nullable=True),
        sa.Column("funding_type", funding_type, nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("agreement_ref", sa.String(120), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_funding_events_company_id", "funding_events", ["company_id"])
    op.create_index("ix_funding_events_funding_type", "funding_events", ["funding_type"])
    op.create_index("ix_funding_events_number", "funding_events", ["number"])

    # default account mappings (investment→301 سرمایه, loan→205 وام, grant→403 کمک,
    # revenue→401 درآمد فروش) — companies existing from earlier migrations get them here
    op.execute(
        "INSERT INTO funding_account_mappings (company_id, funding_type, account_code) "
        "SELECT id, 'investment', '301' FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM funding_account_mappings m WHERE m.company_id = companies.id AND m.funding_type = 'investment')"
    )
    op.execute(
        "INSERT INTO funding_account_mappings (company_id, funding_type, account_code) "
        "SELECT id, 'loan', '205' FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM funding_account_mappings m WHERE m.company_id = companies.id AND m.funding_type = 'loan')"
    )
    op.execute(
        "INSERT INTO funding_account_mappings (company_id, funding_type, account_code) "
        "SELECT id, 'grant', '403' FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM funding_account_mappings m WHERE m.company_id = companies.id AND m.funding_type = 'grant')"
    )
    op.execute(
        "INSERT INTO funding_account_mappings (company_id, funding_type, account_code) "
        "SELECT id, 'revenue', '401' FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM funding_account_mappings m WHERE m.company_id = companies.id AND m.funding_type = 'revenue')"
    )

    # extra chart accounts used by funding (205 وام دریافتی, 403 درآمد کمک بلاعوض)
    op.execute(
        "INSERT INTO accounts (company_id, code, name, type, is_active, is_system) "
        "SELECT id, '205', 'وام دریافتی', 'liability', true, true FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.company_id = companies.id AND a.code = '205')"
    )
    op.execute(
        "INSERT INTO accounts (company_id, code, name, type, is_active, is_system) "
        "SELECT id, '403', 'درآمد کمک بلاعوض', 'revenue', true, true FROM companies "
        "WHERE NOT EXISTS (SELECT 1 FROM accounts a WHERE a.company_id = companies.id AND a.code = '403')"
    )


def downgrade() -> None:
    op.drop_table("funding_events")
    op.drop_table("funding_account_mappings")
    funding_type.drop(op.get_bind(), checkfirst=True)
