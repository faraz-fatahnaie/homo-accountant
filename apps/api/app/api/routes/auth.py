"""Authentication routes: login (rate-limited), refresh (rotated), logout."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import client_ip
from app.api.errors import error_response
from app.core.db import get_db
from app.core.ratelimit import login_limiter
from app.domains.identity.schemas import LoginRequest, RefreshRequest, TokenPair
from app.domains.identity.service import (
    AuthError,
    authenticate,
    issue_token_pair,
    revoke_refresh,
    rotate_refresh,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(
    payload: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenPair | JSONResponse:
    ip = client_ip(request)
    allowed, retry_after = login_limiter.allow(f"login:{ip}")
    if not allowed:
        return error_response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            "تعداد درخواستهای ورود بیش از حد مجاز است؛ کمی بعد دوباره تلاش کنید",
        )  # Retry-After set by middleware

    try:
        user = authenticate(db, payload.email, payload.password)
    except AuthError:
        return error_response(
            status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "ایمیل یا رمز عبور نادرست است"
        )

    pair = issue_token_pair(db, user)
    db.commit()
    logger.info("login ok", extra={"user_id": user.id, "ip": ip})
    return pair


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair | JSONResponse:
    try:
        pair = rotate_refresh(db, payload.refresh_token)
    except AuthError as exc:
        db.rollback()
        return error_response(exc.status_code, "invalid_refresh", exc.message)
    db.commit()
    return pair


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    revoke_refresh(db, payload.refresh_token)
    db.commit()
    return {"status": "ok"}
