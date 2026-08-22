"""Slice 9 hardening tests: security headers, prod surface, upload hygiene."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts


def _seed(client: TestClient, db) -> None:
    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()


class TestSecurityHeaders:
    def test_api_response_headers(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/health/live", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
        assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]
        assert resp.headers["X-Request-ID"]  # correlation id always present

    def test_error_responses_carry_headers(self, client: TestClient, db, auth_headers) -> None:
        """Even 4xx/5xx responses must include security headers (no header leak)."""
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/does-not-exist", headers=headers)
        assert resp.status_code == 404
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_production_disables_docs_and_openapi(
        self, client: TestClient, db, auth_headers
    ) -> None:
        """In production the docs surface is off; in test/dev it stays on."""
        env = os.environ.get("HOMO_ENVIRONMENT", "test")
        if env == "production":
            assert client.get("/docs").status_code == 404
            assert client.get("/openapi.json").status_code == 404
        else:
            assert client.get("/docs").status_code == 200
            assert client.get("/openapi.json").status_code == 200


class TestAttachmentDelivery:
    def test_download_is_attachment_with_nosniff(
        self, client: TestClient, db, auth_headers
    ) -> None:
        """Uploads are served as downloads, never inline (no stored-XSS path)."""
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post(
            "/api/v1/expenses",
            json={
                "entry_date": "2026-08-13",
                "account_code": "603",
                "amount": 1_000_000,
                "payment_method": "bank",
                "description": "پیوست تست",
            },
            headers=headers,
        ).json()
        att = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            files={"file": ("f.pdf", b"%PDF-1.4 minimal", "application/pdf")},
            headers=headers,
        ).json()
        dl = client.get(f"/api/v1/attachments/{att['id']}", headers=headers)
        assert dl.status_code == 200
        assert dl.headers["Content-Disposition"].startswith("attachment")
        assert dl.headers["X-Content-Type-Options"] == "nosniff"
        assert dl.content == b"%PDF-1.4 minimal"


class TestAuthSurface:
    def test_session_cookies_are_http_only_and_same_site(
        self, client: TestClient, db, make_user
    ) -> None:
        user, password = make_user(Role.VIEWER)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login.status_code == 200
        cookies = login.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert all("HttpOnly" in cookie for cookie in cookies)
        assert all("SameSite=lax" in cookie for cookie in cookies)
        assert all("access_token" not in cookie for cookie in cookies)
        assert client.get("/api/v1/users/me").status_code == 200

    def test_unauthenticated_rejected(self, client: TestClient, db) -> None:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] in ("unauthorized", "auth_error")
