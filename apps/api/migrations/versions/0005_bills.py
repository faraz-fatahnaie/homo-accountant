"""Bills, bill payments."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_bills"
down_revision = "0004_invoices"
branch_labels = None
depends_on = None

bill_status = postgresql.ENUM(
    "draft", "open", "partially_paid", "paid", "void", name="bill_status", create_type=False
)


def upgrade() -> None:
    bill_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(30), nullable=True),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("bill_number", sa.String(80), nullable=True),
        sa.Column("status", bill_status, nullable=False, server_default="draft"),
        sa.Column("memo", sa.String(400), nullable=False),
        sa.Column("total", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bills_company_id", "bills", ["company_id"])
    op.create_index("ix_bills_status", "bills", ["status"])
    op.create_index("ix_bills_number", "bills", ["number"])

    op.create_table(
        "bill_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bill_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("reference", sa.String(80), nullable=True),
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bill_payments_bill_id", "bill_payments", ["bill_id"])


def downgrade() -> None:
    op.drop_table("bill_payments")
    op.drop_table("bills")
    bill_status.drop(op.get_bind(), checkfirst=True)
