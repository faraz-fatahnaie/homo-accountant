"""Identity service: companies, users, auth flows, refresh-token lifecycle."""

from __future__ import annotations

import datetime as dt
import logging

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domains.identity.models import Company, RefreshToken, Role, User
from app.domains.identity.schemas import TokenPair

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication/authorization failure (mapped to 401/403 in routes)."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def ensure_default_company(db: Session) -> Company:
    """Return the single MVP company, creating it if absent."""
    company = db.scalar(select(Company).order_by(Company.id).limit(1))
    if company is None:
        company = Company(name="شرکت آریا تجارت", fiscal_year_start=1405)
        db.add(company)
        db.flush()
    return company


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password: str,
    role: Role,
    company: Company | None = None,
) -> User:
    if db.scalar(select(User).where(User.email == email.lower())):
        raise AuthError("کاربر با این ایمیل از قبل وجود دارد", status_code=409)
    company = company or ensure_default_company(db)
    user = User(
        company_id=company.id,
        email=email.lower(),
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    logger.info("user created", extra={"user_id": user.id, "role": role.value})
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active:
        raise AuthError("ایمیل یا رمز عبور نادرست است")
    if not verify_password(password, user.hashed_password):
        raise AuthError("ایمیل یا رمز عبور نادرست است")
    user.last_login_at = dt.datetime.now(dt.UTC)
    db.flush()
    return user


def issue_token_pair(db: Session, user: User) -> TokenPair:
    settings = get_settings()
    access = create_access_token(str(user.id), user.role.value)
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=settings.refresh_token_days),
        )
    )
    db.flush()
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_minutes * 60,
    )


def rotate_refresh(db: Session, raw_refresh: str) -> TokenPair:
    """Validate a refresh token, revoke it, and issue a fresh pair (rotation)."""
    token_hash = hash_token(raw_refresh)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record is None:
        raise AuthError("نشست نامعتبر است یا منقضی شده")
    now = dt.datetime.now(dt.UTC)
    if record.revoked_at is not None:
        # Reuse of a revoked token: revoke the whole family defensively.
        _revoke_family(db, record.user_id)
        raise AuthError("نشست نامعتبر است یا منقضی شده")
    if record.expires_at < now:
        raise AuthError("نشست منقضی شده؛ دوباره وارد شوید")
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise AuthError("حساب کاربری غیرفعال است")
    record.revoked_at = now
    db.flush()
    return issue_token_pair(db, user)


def _revoke_family(db: Session, user_id: int) -> None:
    now = dt.datetime.now(dt.UTC)
    for r in db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    ):
        r.revoked_at = now
    db.flush()


def revoke_refresh(db: Session, raw_refresh: str) -> None:
    record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
    )
    if record is not None and record.revoked_at is None:
        record.revoked_at = dt.datetime.now(dt.UTC)
        db.flush()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


def resolve_access_token(db: Session, token: str) -> User:
    """Validate access JWT and return the live user (raises AuthError)."""
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[get_settings().jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise AuthError("نشست نامعتبر است یا منقضی شده") from exc
    if payload.get("type") != "access":
        raise AuthError("نشست نامعتبر است یا منقضی شده")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("حساب کاربری غیرفعال است")
    return user
