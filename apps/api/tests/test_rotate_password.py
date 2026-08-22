from __future__ import annotations

from sqlalchemy import select

from app.core.security import verify_password
from app.domains.identity.models import RefreshToken, User
from app.domains.identity.service import issue_token_pair
from app.scripts import rotate_password


def test_rotate_password_changes_hash_and_revokes_sessions(db, make_user, monkeypatch) -> None:
    user, _ = make_user(email="owner@example.com")
    user_id = user.id
    issue_token_pair(db, user)
    db.commit()
    monkeypatch.setenv("HOMO_ROTATE_USER_EMAIL", user.email)
    monkeypatch.setenv("HOMO_ROTATE_USER_PASSWORD", "new-strong-password-1405")

    monkeypatch.setattr(rotate_password, "SessionLocal", lambda: db)
    assert rotate_password.main() == 0
    refreshed = db.get(User, user_id)
    assert refreshed is not None
    assert verify_password("new-strong-password-1405", refreshed.hashed_password)
    assert db.scalar(select(RefreshToken).where(RefreshToken.user_id == user_id)) is None
