"""Shared application exceptions exposed through the API error envelope."""

from __future__ import annotations


class AppError(Exception):
    """Expected application failure with a stable machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "application_error",
        status_code: int = 422,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
