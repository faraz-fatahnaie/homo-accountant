"""Safe first-admin bootstrap: creates the OWNER account from env.

Usage (inside the api container):
    python -m app.scripts.bootstrap_admin

Environment:
    HOMO_ADMIN_BOOTSTRAP_EMAIL, HOMO_ADMIN_BOOTSTRAP_PASSWORD
"""

from __future__ import annotations

import sys

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.domains.identity.models import Role
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
        ensure_default_company(db)
        try:
            user = create_user(
                db, email=email, full_name="مدیر سامانه", password=password, role=Role.OWNER
            )
            db.commit()
            print(f"admin created: {user.email} (role=owner, id={user.id})")
        except Exception as exc:  # noqa: BLE001 — user exists
            db.rollback()
            print(f"admin not created: {exc}")
            return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
