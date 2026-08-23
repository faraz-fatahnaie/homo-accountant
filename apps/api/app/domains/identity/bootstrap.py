"""Idempotent initialization of required production accounting data."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.funding.service import ensure_default_mappings
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import seed_chart_of_accounts

# Stable, application-specific PostgreSQL advisory-lock key. The lock is held
# until the surrounding transaction commits or rolls back, so concurrent API
# workers cannot both decide that required startup rows are missing.
_SYSTEM_DATA_LOCK_ID = 0x484F4D4F53595344


def ensure_required_system_data(db: Session) -> dict[str, int]:
    """Create only missing system records; never overwrite user accounts."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": _SYSTEM_DATA_LOCK_ID},
    )
    company = ensure_default_company(db)
    return {
        "company_id": company.id,
        "chart_accounts": seed_chart_of_accounts(db, company.id),
        "funding_mappings": ensure_default_mappings(db, company.id),
    }
