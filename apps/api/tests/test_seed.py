"""Tests: demo-user seeding is idempotent and safe."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.domains.identity.models import Role, User
from app.domains.identity.seed import DEMO_USERS, seed_demo_users


def test_seed_creates_one_user_per_role(client: TestClient, db) -> None:
    created = seed_demo_users(db)
    assert created == len(DEMO_USERS)
    users = db.scalars(select(User)).all()
    assert {u.role for u in users} == set(Role)
    # each demo user can log in
    for email, _, password, _role in DEMO_USERS:
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, email


def test_seed_is_idempotent(db) -> None:
    assert seed_demo_users(db) == len(DEMO_USERS)
    assert seed_demo_users(db) == 0  # already present


def test_seed_refuses_production(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    import pytest

    with pytest.raises(RuntimeError):
        seed_demo_users(db=None)  # type: ignore[arg-type]


def test_seed_dev_data_full_bootstrap(db) -> None:
    """seed_dev_data creates users + chart + periods and is idempotent."""
    from sqlalchemy import select

    from app.domains.identity.seed import seed_dev_data
    from app.domains.ledger.models import Account, AccountingPeriod

    first = seed_dev_data(db)
    assert first["users"] == 4
    assert first["chart_accounts"] == 13
    assert first["periods"] == 12
    assert first["contacts"] == 4
    assert first["projects"] == 3

    # idempotent
    again = seed_dev_data(db)
    assert again["users"] == 0
    assert again["chart_accounts"] == 0
    assert again["contacts"] == 0
    assert again["projects"] == 0

    assert len(list(db.scalars(select(Account)))) == 13
    assert len(list(db.scalars(select(AccountingPeriod)))) == 12
