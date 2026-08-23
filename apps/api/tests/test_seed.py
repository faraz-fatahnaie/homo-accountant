"""Tests: demo-user seeding is idempotent and safe."""

from __future__ import annotations

import threading

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.domains.funding.models import FundingAccountMapping
from app.domains.identity.bootstrap import ensure_required_system_data
from app.domains.identity.models import Role, User
from app.domains.identity.seed import DEMO_USERS, seed_demo_users
from app.domains.ledger.models import Account


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
    assert first["funding_mappings"] == 4

    # idempotent
    again = seed_dev_data(db)
    assert again["users"] == 0
    assert again["chart_accounts"] == 0
    assert again["contacts"] == 0
    assert again["projects"] == 0

    assert len(list(db.scalars(select(Account)))) == 15  # 13 starter + 205 وام + 403 کمک
    assert len(list(db.scalars(select(AccountingPeriod)))) == 12


def test_production_system_data_is_complete_idempotent_and_non_destructive(db) -> None:
    """Production startup creates missing invariants without replacing custom records."""
    from sqlalchemy import select

    from app.domains.identity.service import ensure_default_company
    from app.domains.ledger.models import AccountType

    company = ensure_default_company(db)
    custom = Account(
        company_id=company.id,
        code="401",
        name="درآمد پروژه سفارشی",
        type=AccountType.REVENUE,
        is_system=False,
    )
    db.add(custom)
    db.flush()

    first = ensure_required_system_data(db)
    second = ensure_required_system_data(db)

    codes = set(db.scalars(select(Account.code).where(Account.company_id == company.id)))
    assert {"101", "102", "203", "204", "205", "403"}.issubset(codes)
    assert len(list(db.scalars(select(FundingAccountMapping)))) == 4
    assert first["chart_accounts"] > 0
    assert second["chart_accounts"] == 0
    assert second["funding_mappings"] == 0
    db.refresh(custom)
    assert custom.name == "درآمد پروژه سفارشی"
    assert custom.is_system is False


def test_production_system_data_bootstrap_serializes_concurrent_workers() -> None:
    """A second worker waits for the first transaction and then observes its rows."""
    first_seeded = threading.Event()
    allow_first_commit = threading.Event()
    second_started = threading.Event()
    second_finished = threading.Event()
    errors: list[BaseException] = []
    results: list[dict[str, int]] = []

    def first_worker() -> None:
        db = SessionLocal()
        try:
            results.append(ensure_required_system_data(db))
            first_seeded.set()
            assert allow_first_commit.wait(timeout=5)
            db.commit()
        except BaseException as exc:  # pragma: no cover - asserted in parent thread
            db.rollback()
            errors.append(exc)
        finally:
            db.close()

    def second_worker() -> None:
        db = SessionLocal()
        try:
            assert first_seeded.wait(timeout=5)
            second_started.set()
            results.append(ensure_required_system_data(db))
            db.commit()
        except BaseException as exc:  # pragma: no cover - asserted in parent thread
            db.rollback()
            errors.append(exc)
        finally:
            second_finished.set()
            db.close()

    first = threading.Thread(target=first_worker)
    second = threading.Thread(target=second_worker)
    first.start()
    second.start()
    assert second_started.wait(timeout=5)
    assert not second_finished.wait(timeout=0.25)
    allow_first_commit.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(results) == 2
    assert sorted(result["chart_accounts"] for result in results) == [0, 13]
    assert sorted(result["funding_mappings"] for result in results) == [0, 4]
