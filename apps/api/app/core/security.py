"""Password hashing and JWT handling.

Hashing: PBKDF2-HMAC-SHA256 from the standard library (no native deps), with a
per-user random salt and a high iteration count (default 600_000). Stored format:
`pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>`. Iterations are stored per
record so they can be raised later without invalidating old hashes.

Tokens: PyJWT HS256. Access tokens are short-lived; refresh tokens are opaque,
stored hashed in the database (see identity domain) to support revocation/rotation.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import os
import secrets
from typing import Any

import jwt

from app.core.config import get_settings

_ALGO_LABEL = "pbkdf2_sha256"


def hash_password(password: str, iterations: int | None = None) -> str:
    settings = get_settings()
    iters = iterations or settings.password_hash_iterations
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return "$".join(
        [
            _ALGO_LABEL,
            str(iters),
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        ]
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        label, iters_s, salt_b64, hash_b64 = stored.split("$")
        if label != _ALGO_LABEL:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters_s))
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    minutes = expires_minutes or settings.access_token_minutes
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "jti": secrets.token_urlsafe(8),  # unique per token, even within one second
        "iat": now,
        "exp": now + dt.timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on any failure."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload


def hash_token(token: str) -> str:
    """Hash an opaque refresh token for DB storage (plaintext never persisted)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)
