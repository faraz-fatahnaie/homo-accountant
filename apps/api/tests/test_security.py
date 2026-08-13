"""Unit tests: password hashing, JWT handling, refresh-token helpers."""

from __future__ import annotations

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)


class TestPasswordHashing:
    def test_roundtrip(self) -> None:
        stored = hash_password("s3cret-Pass")
        assert stored.startswith("pbkdf2_sha256$")
        assert verify_password("s3cret-Pass", stored)

    def test_wrong_password_rejected(self) -> None:
        stored = hash_password("correct-horse")
        assert not verify_password("wrong-horse", stored)

    def test_unique_salt(self) -> None:
        assert hash_password("same") != hash_password("same")

    def test_malformed_stored_rejected(self) -> None:
        assert not verify_password("x", "not-a-hash")
        assert not verify_password("x", "md5$1$abc$def$ghi")

    def test_custom_iterations(self) -> None:
        stored = hash_password("pw", iterations=1000)
        assert "$1000$" in stored
        assert verify_password("pw", stored)


class TestTokens:
    def test_access_token_roundtrip(self) -> None:
        token = create_access_token("7", "accountant")
        payload = decode_token(token)
        assert payload["sub"] == "7"
        assert payload["role"] == "accountant"
        assert payload["type"] == "access"

    def test_type_mismatch_rejected(self) -> None:
        token = create_access_token("7", "owner")
        with pytest.raises(jwt.PyJWTError):
            decode_token(token, expected_type="refresh")

    def test_expired_token_rejected(self) -> None:
        token = create_access_token("7", "owner", expires_minutes=-1)
        with pytest.raises(jwt.PyJWTError):
            decode_token(token)

    def test_tampered_token_rejected(self) -> None:
        token = create_access_token("7", "owner")
        tampered = token[:-2] + ("ab" if token[-2:] != "ab" else "cd")
        with pytest.raises(jwt.PyJWTError):
            decode_token(tampered)

    def test_wrong_secret_rejected(self) -> None:
        token = create_access_token("7", "owner")
        import jwt as jwtlib

        with pytest.raises(jwtlib.InvalidSignatureError):
            jwtlib.decode(token, "another-secret", algorithms=[get_settings().jwt_algorithm])


class TestRefreshHelpers:
    def test_hash_token_deterministic(self) -> None:
        assert hash_token("abc") == hash_token("abc")
        assert len(hash_token("abc")) == 64

    def test_refresh_token_generation(self) -> None:
        a, b = generate_refresh_token(), generate_refresh_token()
        assert a != b and len(a) >= 32
