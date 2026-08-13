"""Structured JSON logging with request correlation IDs."""

from __future__ import annotations

import logging
import sys

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter (no external dependency)."""

    _RESERVED = {
        "asctime",
        "name",
        "levelname",
        "message",
        "exc_info",
        "exc_text",
        "stack_info",
        "filename",
        "lineno",
        "module",
        "funcName",
        "msecs",
        "relativeCreated",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    settings = get_settings()
    handler: logging.Handler
    if settings.is_production:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s"))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO if settings.is_production else logging.DEBUG)
    # Keep uvicorn access logs structured in production
    logging.getLogger("uvicorn.access").handlers = [handler]
