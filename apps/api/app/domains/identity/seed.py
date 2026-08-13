"""Development seeding: one company, demo users, chart of accounts, periods.

Never run with production credentials; guarded by HOMO_SEED_DEMO_USERS=true and
refused in production environments. `seed_dev_data` is called on API startup in
dev so `docker compose up` works out of the box.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.identity.models import Role
from app.domains.identity.service import create_user, ensure_default_company

logger = logging.getLogger(__name__)

DEMO_USERS: list[tuple[str, str, str, Role]] = [
    ("owner@example.com", "مدیر سامانه", "owner-homo-1405", Role.OWNER),
    ("accountant@example.com", "نگار رضایی", "acct-homo-1405", Role.ACCOUNTANT),
    ("staff@example.com", "سامان کریمی", "staff-homo-1405", Role.STAFF),
    ("viewer@example.com", "مهمان بیننده", "viewer-homo-1405", Role.VIEWER),
]

_FISCAL_YEAR = 1405


def seed_demo_users(db: Session) -> int:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("refusing to seed demo users in production")
    ensure_default_company(db)
    created = 0
    for email, name, password, role in DEMO_USERS:
        try:
            create_user(db, email=email, full_name=name, password=password, role=role)
            created += 1
        except Exception:  # already exists
            db.rollback()
    db.commit()
    return created


def seed_dev_data(db: Session) -> dict[str, int]:
    """Idempotent full dev bootstrap: company + demo users + chart + periods."""
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("refusing to seed dev data in production")

    from app.domains.ledger.service import get_period, seed_chart_of_accounts

    company = ensure_default_company(db)
    users = seed_demo_users(db)
    chart = seed_chart_of_accounts(db, company.id)
    periods = 0
    for month in range(1, 13):
        get_period(db, company.id, _FISCAL_YEAR, month)
        periods += 1
    db.commit()
    return {"users": users, "chart_accounts": chart, "periods": periods}
