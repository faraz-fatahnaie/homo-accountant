"""Consistent error envelope + exception handlers."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.domains.identity.service import AuthError

logger = logging.getLogger(__name__)

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "درخواست نامعتبر است",
    status.HTTP_401_UNAUTHORIZED: "نشست نامعتبر است",
    status.HTTP_403_FORBIDDEN: "دسترسی لازم را ندارید",
    status.HTTP_404_NOT_FOUND: "موردی یافت نشد",
    status.HTTP_405_METHOD_NOT_ALLOWED: "روش درخواست مجاز نیست",
    status.HTTP_409_CONFLICT: "رکورد تکراری یا متناقض است",
    status.HTTP_429_TOO_MANY_REQUESTS: "تعداد درخواستها بیش از حد مجاز است",
}


def error_response(
    status_code: int, code: str, message: str, details: dict[str, object] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _application_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(AuthError)
    async def _auth_error(_: Request, exc: AuthError) -> JSONResponse:
        return error_response(exc.status_code, "auth_error", exc.message)

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = {
            401: "auth_error",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        detail = (
            exc.detail
            if isinstance(exc.detail, str)
            else _HTTP_ERROR_MESSAGES.get(exc.status_code, "خطا")
        )
        return error_response(exc.status_code, code, detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = {}
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
            details[loc] = err.get("msg", "invalid")
        return error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "ورودی نامعتبر است",
            details,
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("integrity error on %s", request.url.path, extra={"exc": str(exc.orig)})
        return error_response(status.HTTP_409_CONFLICT, "conflict", "رکورد تکراری یا متناقض است")
