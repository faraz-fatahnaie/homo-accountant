"""Test fixtures: real PostgreSQL (arya_test), migrations applied, per-test cleanup.

Environment variables are set BEFORE importing app modules so the cached settings
and engine bind to the test database.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "HOMO_DATABASE_URL", "postgresql+psycopg://arya:arya_dev_pw@127.0.0.1:5432/arya_test"
)
os.environ.setdefault("HOMO_JWT_SECRET", "test-only-secret-0123456789abcdef")
os.environ.setdefault("HOMO_LOGIN_RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("HOMO_ENVIRONMENT", "test")
# Upload tests write attachments to a scratch dir, never to the repo's media/
os.environ.setdefault("HOMO_MEDIA_DIR", tempfile.mkdtemp(prefix="homo-test-media-"))

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.domains.identity.models import Role  # noqa: E402
from app.domains.identity.service import create_user, ensure_default_company  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> None:
    """Apply migrations to the test database once per session (real migration test)."""
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db: None) -> None:
    """Truncate all tables (except alembic_version) before each test."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE attachments, expenses, projects, contacts, "
                "invoice_payments, invoice_items, invoices, "
                "bill_payments, bills, "
                "funding_events, funding_account_mappings, "
                "saved_queries, "
                "refresh_tokens, users, companies RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def company_id(db: Session) -> int:
    return ensure_default_company(db).id


@pytest.fixture
def make_user(db: Session):
    """Factory: create a user with a known password and return (user, password)."""

    def _make(
        role: Role = Role.ACCOUNTANT, email: str | None = None, password: str = "test-pass-12345"
    ):
        user = create_user(
            db,
            email=email or f"{role.value}@example.com",
            full_name=f"کاربر {role.value}",
            password=password,
            role=role,
        )
        db.commit()
        return user, password

    return _make


@pytest.fixture
def auth_headers(client: TestClient, make_user):
    """Return (headers, user) for a logged-in user of a given role."""

    def _auth(role: Role = Role.ACCOUNTANT):
        user, _ = make_user(role)
        token = create_access_token(str(user.id), user.role.value)
        return {"Authorization": f"Bearer {token}"}, user

    return _auth
