"""Development seeding: one company and one user per role.

Never run with production credentials; guarded by HOMO_SEED_DEMO_USERS=true
and refused in production environments.
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
