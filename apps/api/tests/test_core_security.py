from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.http import attachment_disposition


def test_attachment_disposition_removes_header_injection_and_encodes_unicode() -> None:
    value = attachment_disposition('رسید\r\nX-Evil: yes.pdf')
    assert "\r" not in value and "\n" not in value
    assert "filename*=UTF-8''" in value
    assert "%D8%B1" in value


def test_production_rejects_default_secret_and_database_password() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_secret="a-unique-production-secret-at-least-32-characters",
            database_url="postgresql+psycopg://app:strong@db/app",
            cors_origins="*",
        )


def test_production_accepts_explicit_secure_configuration() -> None:
    settings = Settings(
        environment="production",
        jwt_secret="a-unique-production-secret-at-least-32-characters",
        database_url="postgresql+psycopg://app:strong@db/app",
        cors_origins="https://mohotec.ir",
    )
    assert settings.is_production
