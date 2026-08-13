"""Health/liveness/readiness endpoints for orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> Response:
    try:
        db.execute(text("SELECT 1"))
        return Response(
            content='{"status":"ready"}',
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
    except Exception:
        return Response(
            content='{"status":"not_ready"}',
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
