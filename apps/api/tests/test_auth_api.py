"""API tests: authentication flows and RBAC (server-enforced)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domains.identity.models import Role


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


class TestLogin:
    def test_login_success_returns_token_pair(self, client: TestClient, make_user) -> None:
        user, password = make_user(Role.ACCOUNTANT)
        resp = _login(client, user.email, password)
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["expires_in"] > 0

    def test_login_wrong_password(self, client: TestClient, make_user) -> None:
        user, _ = make_user(Role.STAFF)
        resp = _login(client, user.email, "wrong-password-99")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_credentials"

    def test_login_unknown_email(self, client: TestClient) -> None:
        resp = _login(client, "nobody@example.com", "whatever-12345")
        assert resp.status_code == 401

    def test_login_inactive_user(self, client: TestClient, db, make_user) -> None:
        user, password = make_user(Role.VIEWER)
        user.is_active = False
        db.commit()
        resp = _login(client, user.email, password)
        assert resp.status_code == 401

    def test_login_validation_error(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "x"})
        assert resp.status_code == 422
        body = resp.json()["error"]
        assert body["code"] == "validation_error"
        assert "email" in body["details"]

    def test_login_rate_limited(self, client: TestClient, make_user, monkeypatch) -> None:
        import app.api.routes.auth as auth_routes
        from app.core.ratelimit import SlidingWindowLimiter

        user, password = make_user(Role.ACCOUNTANT)
        monkeypatch.setattr(auth_routes, "login_limiter", SlidingWindowLimiter(2, 60.0))
        assert _login(client, user.email, password).status_code == 200
        assert _login(client, user.email, password).status_code == 200
        resp = _login(client, user.email, password)
        assert resp.status_code == 429
        assert resp.headers.get("retry-after") or resp.json()["error"]["code"] == "rate_limited"


class TestRefreshRotation:
    def test_refresh_rotates_and_old_is_rejected(self, client: TestClient, make_user) -> None:
        user, password = make_user(Role.ACCOUNTANT)
        pair = _login(client, user.email, password).json()
        # first refresh works
        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert r1.status_code == 200
        new_pair = r1.json()
        assert new_pair["access_token"] != pair["access_token"]
        # old refresh token is now revoked -> reuse detection
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert r2.status_code == 401
        # the rotated token still works
        r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_pair["refresh_token"]})
        assert r3.status_code == 200

    def test_refresh_invalid_token(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage-token"})
        assert resp.status_code == 401

    def test_logout_revokes_refresh(self, client: TestClient, make_user) -> None:
        user, password = make_user(Role.STAFF)
        pair = _login(client, user.email, password).json()
        resp = client.post("/api/v1/auth/logout", json={"refresh_token": pair["refresh_token"]})
        assert resp.status_code == 200
        after = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
        assert after.status_code == 401


class TestMe:
    def test_me_returns_user(self, client: TestClient, auth_headers) -> None:
        headers, user = auth_headers(Role.ACCOUNTANT)
        resp = client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user.email
        assert body["role"] == "accountant"
        assert body["full_name"] == user.full_name

    def test_me_without_token(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_me_with_garbage_token(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer nope.nope.nope"})
        assert resp.status_code == 401


class TestRbac:
    """RBAC must be enforced by the API even when called directly."""

    def test_users_list_owner_only(self, client: TestClient, auth_headers) -> None:
        headers, _ = auth_headers(Role.OWNER)
        resp = client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.parametrize("role", [Role.ACCOUNTANT, Role.STAFF, Role.VIEWER])
    def test_users_list_forbidden_for_other_roles(
        self, client: TestClient, auth_headers, role: Role
    ) -> None:
        headers, _ = auth_headers(role)
        resp = client.get("/api/v1/users", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"

    def test_users_list_anonymous(self, client: TestClient) -> None:
        assert client.get("/api/v1/users").status_code == 401

    def test_create_user_owner_only(self, client: TestClient, auth_headers) -> None:
        headers, _ = auth_headers(Role.OWNER)
        resp = client.post(
            "/api/v1/users",
            json={
                "email": "new@example.com",
                "full_name": "کاربر جدید",
                "password": "strong-pass-123",
                "role": "staff",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["email"] == "new@example.com"

    def test_create_user_duplicate_email(self, client: TestClient, auth_headers, make_user) -> None:
        user, _ = make_user(Role.STAFF)
        headers, _ = auth_headers(Role.OWNER)
        resp = client.post(
            "/api/v1/users",
            json={
                "email": user.email,
                "full_name": "تکراری",
                "password": "strong-pass-123",
                "role": "staff",
            },
            headers=headers,
        )
        assert resp.status_code == 409

    def test_staff_cannot_create_user(self, client: TestClient, auth_headers) -> None:
        headers, _ = auth_headers(Role.STAFF)
        resp = client.post(
            "/api/v1/users",
            json={
                "email": "x@example.com",
                "full_name": "x",
                "password": "strong-pass-123",
                "role": "staff",
            },
            headers=headers,
        )
        assert resp.status_code == 403
