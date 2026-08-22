"""Authentication routes: login (rate-limited), refresh (rotated), logout."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import client_ip
from app.api.errors import error_response
from app.core.config import get_settings
from app.core.db import get_db
from app.core.ratelimit import login_limiter
from app.domains.identity.schemas import LoginRequest, SessionOut, TokenPair
from app.domains.identity.service import (
    AuthError,
    authenticate,
    issue_token_pair,
    revoke_refresh,
    rotate_refresh,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, pair: TokenPair) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.access_cookie_name,
        pair.access_token,
        max_age=pair.expires_in,
        path="/api",
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        pair.refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path=f"{settings.api_prefix}/auth",
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
    )


def _clear_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(settings.access_cookie_name, path="/api")
    response.delete_cookie(settings.refresh_cookie_name, path=f"{settings.api_prefix}/auth")


@router.post("/login", response_model=SessionOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SessionOut | JSONResponse:
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
    _set_session_cookies(response, pair)
    logger.info("login ok", extra={"user_id": user.id, "ip": ip})
    return SessionOut(expires_in=pair.expires_in)


@router.post("/refresh", response_model=SessionOut)
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> SessionOut | JSONResponse:
    settings = get_settings()
    raw_refresh = request.cookies.get(settings.refresh_cookie_name)
    if not raw_refresh:
        result = error_response(401, "invalid_refresh", "نشست نامعتبر است یا منقضی شده")
        _clear_session_cookies(result)
        return result
    try:
        pair = rotate_refresh(db, raw_refresh)
    except AuthError as exc:
        if exc.code == "refresh_reused":
            db.commit()
        else:
            db.rollback()
        result = error_response(exc.status_code, "invalid_refresh", exc.message)
        _clear_session_cookies(result)
        return result
    db.commit()
    _set_session_cookies(response, pair)
    return SessionOut(expires_in=pair.expires_in)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    settings = get_settings()
    raw_refresh = request.cookies.get(settings.refresh_cookie_name)
    if raw_refresh:
        revoke_refresh(db, raw_refresh)
    db.commit()
    _clear_session_cookies(response)
    return {"status": "ok"}
