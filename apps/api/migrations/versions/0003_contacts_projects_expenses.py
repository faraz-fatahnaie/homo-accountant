"""Contacts, projects, expenses, attachments + per-kind sequence refs."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_contacts_projects_expenses"
down_revision = "0002_ledger"
branch_labels = None
depends_on = None

payment_method = postgresql.ENUM("cash", "bank", "online", name="payment_method", create_type=False)
expense_status = postgresql.ENUM("draft", "posted", "voided", name="expense_status", create_type=False)
project_status = postgresql.ENUM("active", "completed", "on_hold", name="project_status", create_type=False)


def upgrade() -> None:
    payment_method.create(op.get_bind(), checkfirst=True)
    expense_status.create(op.get_bind(), checkfirst=True)
    project_status.create(op.get_bind(), checkfirst=True)

    # ---- contacts (unified counterparty; multi-role via array) ----
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("roles", postgresql.ARRAY(sa.String(30)), nullable=False, server_default="{}"),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("national_id", sa.String(40), nullable=True),
        sa.Column("address", sa.String(400), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])

    # ---- projects ----
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", project_status, nullable=False, server_default="active"),
        sa.Column("description", sa.String(600), nullable=True),
        sa.Column("responsible_person", sa.String(200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("budget", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_company_id", "projects", ["company_id"])

    # ---- expenses ----
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("number", sa.String(30), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False, server_default="cash"),
        sa.Column("reference", sa.String(80), nullable=True),
        sa.Column("description", sa.String(400), nullable=False),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("status", expense_status, nullable=False, server_default="draft"),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expenses_company_id", "expenses", ["company_id"])
    op.create_index("ix_expenses_status", "expenses", ["status"])
    op.create_index("ix_expenses_number", "expenses", ["number"])

    # ---- attachments (expense receipts) ----
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("owner_type", sa.String(30), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_attachments_company_id", "attachments", ["company_id"])
    op.create_index("ix_attachments_owner", "attachments", ["owner_type", "owner_id"])

    # ---- per-kind sequence references (J stays default; EXP etc. added) ----
    op.add_column(
        "period_sequences",
        sa.Column("kind", sa.String(10), nullable=False, server_default="J"),
    )
    op.drop_constraint("uq_seq_company_ym", "period_sequences", type_="unique")
    op.create_unique_constraint(
        "uq_seq_company_ym_kind", "period_sequences", ["company_id", "year", "month", "kind"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_seq_company_ym_kind", "period_sequences", type_="unique")
    op.create_unique_constraint("uq_seq_company_ym", "period_sequences", ["company_id", "year", "month"])
    op.drop_column("period_sequences", "kind")
    op.drop_table("attachments")
    op.drop_table("expenses")
    op.drop_table("projects")
    op.drop_table("contacts")
    project_status.drop(op.get_bind(), checkfirst=True)
    expense_status.drop(op.get_bind(), checkfirst=True)
    payment_method.drop(op.get_bind(), checkfirst=True)
