"""Idempotent initialization of required production accounting data."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.funding.service import ensure_default_mappings
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import seed_chart_of_accounts


def ensure_required_system_data(db: Session) -> dict[str, int]:
    """Create only missing system records; never overwrite user accounts."""
    company = ensure_default_company(db)
    return {
        "company_id": company.id,
        "chart_accounts": seed_chart_of_accounts(db, company.id),
        "funding_mappings": ensure_default_mappings(db, company.id),
    }
