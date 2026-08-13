"""API tests: contacts + projects (CRUD + RBAC)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company


def _seed(client: TestClient, db) -> None:
    ensure_default_company(db)
    db.commit()


class TestContactsApi:
    def test_create_and_list_contact(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/contacts",
            json={
                "name": "بازرگانی خلیجفارس",
                "roles": ["customer"],
                "phone": "021-88765432",
                "payment_terms_days": 30,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "بازرگانی خلیجفارس"
        assert body["roles"] == ["customer"]

        listed = client.get("/api/v1/contacts", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

    def test_contact_multiple_roles_deduped(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/contacts",
            json={"name": "شرکت امید", "roles": ["investor", "customer", "customer"]},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["roles"] == ["investor", "customer"]

    def test_invalid_role_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/contacts", json={"name": "x", "roles": ["hacker"]}, headers=headers
        )
        assert resp.status_code == 422

    def test_staff_cannot_create_contact(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.STAFF)
        resp = client.post("/api/v1/contacts", json={"name": "x"}, headers=headers)
        assert resp.status_code == 403

    def test_viewer_can_read_contacts(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        client.post("/api/v1/contacts", json={"name": "مشتری الف"}, headers=headers)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/contacts", headers=viewer)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_update_contact(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/contacts", json={"name": "الف"}, headers=headers).json()
        resp = client.patch(
            f"/api/v1/contacts/{created['id']}",
            json={"phone": "0912-0000000", "roles": ["vendor"]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "0912-0000000"
        assert resp.json()["roles"] == ["vendor"]


class TestProjectsApi:
    def test_create_and_list_project(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/projects",
            json={
                "name": "بازسازی انبار",
                "budget": 500_000_000,
                "status": "active",
                "responsible_person": "نگار رضایی",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["budget"] == 500_000_000

        listed = client.get("/api/v1/projects", headers=headers)
        assert len(listed.json()) == 1

    def test_negative_budget_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/projects", json={"name": "x", "budget": -1}, headers=headers)
        assert resp.status_code == 422

    def test_end_before_start_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/projects",
            json={"name": "x", "start_date": "2026-09-01", "end_date": "2026-08-01"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_staff_cannot_create_project(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.STAFF)
        resp = client.post("/api/v1/projects", json={"name": "x"}, headers=headers)
        assert resp.status_code == 403

    def test_update_project(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/projects", json={"name": "الف"}, headers=headers).json()
        resp = client.patch(
            f"/api/v1/projects/{created['id']}",
            json={"status": "completed", "budget": 120_000_000},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
