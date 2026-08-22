"""Guarantee one reversal per posted journal entry."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_unique_reversal"
down_revision = "0007_saved_queries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy versions could create two reversals for one original. Preserve
    # every posted line and repair the net ledger effect before enforcing the
    # invariant: the earliest reversal stays linked to the original; each
    # additional reversal becomes a standalone erroneous entry and receives
    # its own balancing correction entry.
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                duplicate RECORD;
                correction_id INTEGER;
            BEGIN
                FOR duplicate IN
                    SELECT id, company_id, entry_date, memo, posted_by_id
                    FROM (
                        SELECT je.*,
                               row_number() OVER (
                                   PARTITION BY reversal_of_id ORDER BY id
                               ) AS reversal_rank
                        FROM journal_entries AS je
                        WHERE reversal_of_id IS NOT NULL
                    ) AS ranked
                    WHERE reversal_rank > 1
                    ORDER BY id
                LOOP
                    UPDATE journal_entries
                    SET reversal_of_id = NULL
                    WHERE id = duplicate.id;

                    INSERT INTO journal_entries (
                        company_id, entry_date, reference, memo, status,
                        reversal_of_id, created_by_id, posted_by_id, posted_at
                    )
                    VALUES (
                        duplicate.company_id,
                        duplicate.entry_date,
                        'MIG-REV-' || duplicate.id,
                        'اصلاح سیستمی برگشت تکراری سند ' || duplicate.id,
                        'posted'::journal_status,
                        duplicate.id,
                        duplicate.posted_by_id,
                        duplicate.posted_by_id,
                        now()
                    )
                    RETURNING id INTO correction_id;

                    INSERT INTO journal_lines (entry_id, account_id, debit, credit)
                    SELECT correction_id, account_id, credit, debit
                    FROM journal_lines
                    WHERE entry_id = duplicate.id;
                END LOOP;
            END $$;
            """
        )
    )
    op.create_unique_constraint(
        "uq_journal_entries_reversal_of",
        "journal_entries",
        ["reversal_of_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_journal_entries_reversal_of",
        "journal_entries",
        type_="unique",
    )
