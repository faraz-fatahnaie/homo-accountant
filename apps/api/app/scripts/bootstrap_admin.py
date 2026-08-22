"""Safe first-admin bootstrap: creates the OWNER account from env.

Usage (inside the api container):
    python -m app.scripts.bootstrap_admin

Environment:
    HOMO_ADMIN_BOOTSTRAP_EMAIL, HOMO_ADMIN_BOOTSTRAP_PASSWORD
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.domains.identity.bootstrap import ensure_required_system_data
from app.domains.identity.models import Role, User
from app.domains.identity.service import create_user, ensure_default_company


def main() -> int:
    settings = get_settings()
    email = settings.admin_bootstrap_email.strip()
    password = settings.admin_bootstrap_password

    if not email or not password:
        print(
            "bootstrap_admin: HOMO_ADMIN_BOOTSTRAP_EMAIL / HOMO_ADMIN_BOOTSTRAP_PASSWORD "
            "must be set (or pass email/password interactively next).",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    try:
        company = ensure_default_company(db)
        initialized = ensure_required_system_data(db)
        existing = db.scalar(select(User).where(User.email == email.lower()))
        if existing is None:
            user = create_user(
                db,
                email=email,
                full_name="مدیر سامانه",
                password=password,
                role=Role.OWNER,
                company=company,
            )
            outcome = "created"
        else:
            user = existing
            outcome = "already exists"
        db.commit()
        print(
            f"admin {outcome}: {user.email} (role={user.role.value}, id={user.id}); "
            f"chart+{initialized['chart_accounts']}, mappings+{initialized['funding_mappings']}"
        )
    except Exception as exc:  # noqa: BLE001 — operational CLI reports exact failure
        db.rollback()
        print(f"bootstrap_admin failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
