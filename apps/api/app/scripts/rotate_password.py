"""Rotate one user's password and revoke all active sessions.

Usage inside the API container::

    HOMO_ROTATE_USER_EMAIL=owner@example.com \
    HOMO_ROTATE_USER_PASSWORD='a-new-long-password' \
    python -m app.scripts.rotate_password

The password is never printed or accepted as a command-line argument, which
keeps it out of process listings and shell history when supplied securely.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import delete, select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domains.identity.models import RefreshToken, User


def main() -> int:
    email = os.environ.get("HOMO_ROTATE_USER_EMAIL", "").strip().lower()
    password = os.environ.get("HOMO_ROTATE_USER_PASSWORD", "")
    if not email or not 10 <= len(password) <= 128:
        print(
            "rotate_password: set HOMO_ROTATE_USER_EMAIL and a 10–128 character "
            "HOMO_ROTATE_USER_PASSWORD",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        if user is None:
            print("rotate_password: user not found", file=sys.stderr)
            return 3
        user.hashed_password = hash_password(password)
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        db.commit()
        print(f"password rotated and sessions revoked for user id={user.id}")
    except Exception as exc:  # noqa: BLE001 — operational CLI reports failure
        db.rollback()
        print(f"rotate_password failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
