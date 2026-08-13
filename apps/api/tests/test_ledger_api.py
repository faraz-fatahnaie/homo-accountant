"""API tests: ledger contract + RBAC enforcement (server-side)."""

from __future__ import annotations

import datetime as dt

import httpx
from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts

ENTRY_DATE = dt.date(2026, 8, 13).isoformat()  # 1405/05/22


def _seed(client: TestClient, db) -> int:
    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()
    return company.id


def _create_entry(
    client: TestClient, headers: dict[str, str], **overrides: object
) -> httpx.Response:
    payload: dict[str, object] = {
        "entry_date": ENTRY_DATE,
        "memo": "هزینه مواد اولیه",
        "lines": [
            {"account_code": "603", "debit": 48_500_000, "credit": 0},
            {"account_code": "102", "debit": 0, "credit": 48_500_000},
        ],
    }
    payload.update(overrides)
    return client.post("/api/v1/journal-entries", json=payload, headers=headers)


class TestAccountsApi:
    def test_list_accounts(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/accounts", headers=headers)
        assert resp.status_code == 200
        codes = [a["code"] for a in resp.json()]
        assert "101" in codes and "603" in codes

    def test_create_account_accountant_ok(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/accounts",
            json={"code": "104", "name": "بانک ملت", "type": "asset"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["code"] == "104"

    def test_create_account_staff_forbidden(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.STAFF)
        resp = client.post(
            "/api/v1/accounts",
            json={"code": "104", "name": "بانک ملت", "type": "asset"},
            headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "forbidden"

    def test_create_account_viewer_forbidden(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.post(
            "/api/v1/accounts",
            json={"code": "104", "name": "بانک ملت", "type": "asset"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_duplicate_code_conflict(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/accounts",
            json={"code": "101", "name": "تکراری", "type": "asset"},
            headers=headers,
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "account_code_taken"

    def test_system_account_cannot_be_renamed(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        accounts = client.get("/api/v1/accounts", headers=headers).json()
        system = next(a for a in accounts if a["code"] == "101")
        resp = client.patch(
            f"/api/v1/accounts/{system['id']}",
            json={"name": "اسم جدید"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_system"


class TestJournalApi:
    def test_draft_then_post_flow(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(client, headers)
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "draft"
        assert body["lines"][0]["account_code"] == "603"

        posted = client.post(f"/api/v1/journal-entries/{body['id']}/post", headers=headers)
        assert posted.status_code == 200
        assert posted.json()["status"] == "posted"
        assert posted.json()["reference"] == "J-1405-0001"

    def test_unbalanced_rejected_by_api(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(
            client,
            headers,
            lines=[
                {"account_code": "603", "debit": 50_000_000, "credit": 0},
                {"account_code": "102", "debit": 0, "credit": 48_500_000},
            ],
        )
        assert created.status_code == 201
        resp = client.post(f"/api/v1/journal-entries/{created.json()['id']}/post", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "unbalanced_entry"

    def test_staff_cannot_create_entry(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.STAFF)
        resp = _create_entry(client, headers)
        assert resp.status_code == 403

    def test_viewer_cannot_post(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct_headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(client, acct_headers)
        viewer_headers, _ = auth_headers(Role.VIEWER)
        resp = client.post(
            f"/api/v1/journal-entries/{created.json()['id']}/post", headers=viewer_headers
        )
        assert resp.status_code == 403

    def test_read_entry_as_viewer_ok(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct_headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(client, acct_headers)
        viewer_headers, _ = auth_headers(Role.VIEWER)
        resp = client.get(f"/api/v1/journal-entries/{created.json()['id']}", headers=viewer_headers)
        assert resp.status_code == 200
        assert resp.json()["memo"] == "هزینه مواد اولیه"

    def test_void_via_api(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(client, headers)
        client.post(f"/api/v1/journal-entries/{created.json()['id']}/post", headers=headers)
        resp = client.post(f"/api/v1/journal-entries/{created.json()['id']}/void", headers=headers)
        assert resp.status_code == 200
        reversal = resp.json()
        assert reversal["status"] == "posted"
        assert reversal["reversal_of_id"] == created.json()["id"]
        assert reversal["memo"].startswith("برگشتی")

    def test_anonymous_cannot_read(self, client: TestClient, db) -> None:
        _seed(client, db)
        resp = client.get("/api/v1/journal-entries")
        assert resp.status_code == 401


class TestPeriodsApi:
    def test_close_then_post_rejected_then_reopen(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        acct_headers, _ = auth_headers(Role.ACCOUNTANT)
        owner_headers, _ = auth_headers(Role.OWNER)

        periods = client.get("/api/v1/periods", headers=acct_headers).json()
        period = next(p for p in periods if p["year"] == 1405 and p["month"] == 5)
        assert period["status"] == "open"

        closed = client.post(f"/api/v1/periods/{period['id']}/close", headers=acct_headers)
        assert closed.status_code == 200
        assert closed.json()["status"] == "closed"

        # posting into closed period fails through the API
        created = client.post(
            "/api/v1/journal-entries",
            json={
                "entry_date": ENTRY_DATE,
                "memo": "x",
                "lines": [
                    {"account_code": "603", "debit": 1, "credit": 0},
                    {"account_code": "102", "debit": 0, "credit": 1},
                ],
            },
            headers=acct_headers,
        )
        post = client.post(
            f"/api/v1/journal-entries/{created.json()['id']}/post", headers=acct_headers
        )
        assert post.status_code == 422
        assert post.json()["error"]["code"] == "period_closed"

        # reopen is owner-only
        forbidden = client.post(f"/api/v1/periods/{period['id']}/reopen", headers=acct_headers)
        assert forbidden.status_code == 403
        reopened = client.post(f"/api/v1/periods/{period['id']}/reopen", headers=owner_headers)
        assert reopened.status_code == 200
        assert reopened.json()["status"] == "open"

    def test_staff_cannot_close(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        staff_headers, _ = auth_headers(Role.STAFF)
        periods = client.get("/api/v1/periods", headers=staff_headers).json()
        period = periods[0]
        resp = client.post(f"/api/v1/periods/{period['id']}/close", headers=staff_headers)
        assert resp.status_code == 403


class TestBalancesApi:
    def test_balances_endpoint_readable_by_viewer(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        acct_headers, _ = auth_headers(Role.ACCOUNTANT)
        created = _create_entry(client, acct_headers)
        client.post(f"/api/v1/journal-entries/{created.json()['id']}/post", headers=acct_headers)
        viewer_headers, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/accounts/balances", headers=viewer_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        b102 = next(b for b in data if b["code"] == "102")
        assert b102["balance"] == -48_500_000
        b603 = next(b for b in data if b["code"] == "603")
        assert b603["balance"] == 48_500_000

    def test_balances_anonymous_401(self, client: TestClient, db) -> None:
        _seed(client, db)
        resp = client.get("/api/v1/accounts/balances")
        assert resp.status_code == 401
