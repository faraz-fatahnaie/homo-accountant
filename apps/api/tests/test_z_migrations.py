"""Migration reversibility test (runs last; recreates the schema).

Verifies downgrade-to-base and upgrade-to-head both succeed — the same
operations `alembic downgrade base && alembic upgrade head` would perform.
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config as AlembicConfig


def test_migrations_downgrade_and_upgrade() -> None:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
