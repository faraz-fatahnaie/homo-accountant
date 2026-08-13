"""FastAPI application entrypoint: middleware, routes, error handlers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import register_error_handlers
from app.api.routes import auth, health, users
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# --- CORS (narrow allowlist) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def security_and_trace(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Security headers + correlation IDs + safe default responses."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    headers = {
        "X-Request-ID": request_id,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    }
    if settings.is_production:
        headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        logger.exception("unhandled error", extra={"request_id": request_id})
        response = JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "خطای داخلی سرور"}},
        )
    for key, value in headers.items():
        response.headers[key] = value
    response.headers["X-RateLimit-By"] = "auth"
    return response


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(users.router, prefix=settings.api_prefix)

register_error_handlers(app)


@app.get("/")
def root() -> dict[str, str | None]:
    return {"app": settings.app_name, "docs": "/docs" if not settings.is_production else None}
