"""Shared FastAPI dependencies: auth, RBAC, DB session."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.domains.identity.models import Role, User
from app.domains.identity.service import AuthError, resolve_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = (
        credentials.credentials
        if credentials is not None
        else request.cookies.get(get_settings().access_cookie_name)
    )
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="نشست نامعتبر است")
    try:
        return resolve_access_token(db, token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="نشست نامعتبر است") from exc


def require_roles(*roles: Role) -> Callable[..., User]:
    """RBAC dependency factory: allow only the given roles (server-enforced)."""

    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="دسترسی لازم را ندارید")
        return user

    return checker


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
