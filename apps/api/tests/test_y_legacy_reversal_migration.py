"""Regression test for migration 0008's non-destructive ledger repair."""

from __future__ import annotations

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import text

from app.core.db import engine


def test_duplicate_legacy_reversals_are_balanced_and_relinked() -> None:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    command.downgrade(cfg, "0007_saved_queries")

    with engine.begin() as conn:
        company_id = conn.scalar(
            text(
                "INSERT INTO companies (name, fiscal_year_start) "
                "VALUES ('legacy', 1405) RETURNING id"
            )
        )
        debit_account = conn.scalar(
            text(
                "INSERT INTO accounts (company_id, code, name, type, is_active, is_system) "
                "VALUES (:company, '101', 'cash', 'asset', true, true) RETURNING id"
            ),
            {"company": company_id},
        )
        credit_account = conn.scalar(
            text(
                "INSERT INTO accounts (company_id, code, name, type, is_active, is_system) "
                "VALUES (:company, '301', 'equity', 'equity', true, true) RETURNING id"
            ),
            {"company": company_id},
        )
        original_id = conn.scalar(
            text(
                "INSERT INTO journal_entries (company_id, entry_date, memo, status, posted_at) "
                "VALUES (:company, '2026-08-22', 'original', 'posted', now()) RETURNING id"
            ),
            {"company": company_id},
        )
        conn.execute(
            text(
                "INSERT INTO journal_lines (entry_id, account_id, debit, credit) VALUES "
                "(:entry, :debit_account, 100, 0), (:entry, :credit_account, 0, 100)"
            ),
            {
                "entry": original_id,
                "debit_account": debit_account,
                "credit_account": credit_account,
            },
        )
        reversal_ids: list[int] = []
        for memo in ("first reversal", "duplicate reversal"):
            reversal_id = conn.scalar(
                text(
                    "INSERT INTO journal_entries "
                    "(company_id, entry_date, memo, status, reversal_of_id, posted_at) "
                    "VALUES (:company, '2026-08-22', :memo, 'posted', :original, now()) "
                    "RETURNING id"
                ),
                {"company": company_id, "memo": memo, "original": original_id},
            )
            assert reversal_id is not None
            reversal_ids.append(reversal_id)
            conn.execute(
                text(
                    "INSERT INTO journal_lines (entry_id, account_id, debit, credit) VALUES "
                    "(:entry, :debit_account, 0, 100), (:entry, :credit_account, 100, 0)"
                ),
                {
                    "entry": reversal_id,
                    "debit_account": debit_account,
                    "credit_account": credit_account,
                },
            )

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        links_to_original = conn.scalar(
            text("SELECT count(*) FROM journal_entries WHERE reversal_of_id = :original"),
            {"original": original_id},
        )
        correction_id = conn.scalar(
            text("SELECT id FROM journal_entries WHERE reversal_of_id = :duplicate"),
            {"duplicate": reversal_ids[1]},
        )
        extra_parent = conn.scalar(
            text("SELECT reversal_of_id FROM journal_entries WHERE id = :duplicate"),
            {"duplicate": reversal_ids[1]},
        )
        net = conn.execute(
            text(
                "SELECT sum(debit), sum(credit) FROM journal_lines "
                "WHERE entry_id IN (:original, :first, :duplicate, :correction)"
            ),
            {
                "original": original_id,
                "first": reversal_ids[0],
                "duplicate": reversal_ids[1],
                "correction": correction_id,
            },
        ).one()
        account_nets = conn.execute(
            text(
                "SELECT account_id, sum(debit) - sum(credit) AS balance "
                "FROM journal_lines "
                "WHERE entry_id IN (:original, :first, :duplicate, :correction) "
                "GROUP BY account_id"
            ),
            {
                "original": original_id,
                "first": reversal_ids[0],
                "duplicate": reversal_ids[1],
                "correction": correction_id,
            },
        ).all()

    assert links_to_original == 1
    assert correction_id is not None
    assert extra_parent is None
    assert net[0] == net[1] == 400
    assert {balance for _, balance in account_nets} == {0}
