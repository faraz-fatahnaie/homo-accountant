"""Service + API tests: funding events (investment/loan/grant/revenue) + mappings."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts


def _seed(client: TestClient, db) -> None:
    from app.domains.funding.service import ensure_default_mappings

    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    ensure_default_mappings(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()


def _investor(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/v1/contacts",
        json={"name": "شرکت سرمایهگذاری امید", "roles": ["investor"]},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _lender(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/v1/contacts", json={"name": "بانک ملت", "roles": ["lender"]}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _funding_payload(funding_type: str, **overrides) -> dict:
    payload: dict = {
        "funding_type": funding_type,
        "event_date": "2026-08-10",
        "amount": 100_000_000,
        "method": "bank",
    }
    payload.update(overrides)
    return payload


class TestFundingEventsApi:
    def test_investment_posts_to_equity(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _investor(client, headers)
        resp = client.post(
            "/api/v1/funding",
            json=_funding_payload("investment", contact_id=cid, agreement_ref="قرارداد ۱۴۰۵-۰۱"),
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["number"] == "FDG-1405-0001"
        assert body["status"] == "posted"
        assert body["journal_entry_id"] is not None

        entry = client.get(
            f"/api/v1/journal-entries/{body['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"102", "301"}  # Dr bank / Cr سرمایه مالک — NOT revenue
        credit = {ln["account_code"]: ln["credit"] for ln in entry["lines"]}
        assert credit["301"] == 100_000_000

    def test_loan_posts_to_loan_account_and_needs_maturity(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _lender(client, headers)

        # missing maturity -> rejected
        resp = client.post(
            "/api/v1/funding", json=_funding_payload("loan", contact_id=cid), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "loan_maturity_required"

        # with maturity -> Dr bank / Cr 205 وام دریافتی (NOT revenue)
        resp = client.post(
            "/api/v1/funding",
            json=_funding_payload(
                "loan", contact_id=cid, maturity_date="2027-08-10", agreement_ref="تسهیلات ۵۰۰"
            ),
            headers=headers,
        )
        assert resp.status_code == 201
        entry = client.get(
            f"/api/v1/journal-entries/{resp.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"102", "205"}

    def test_grant_posts_to_grant_revenue(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/funding", json=_funding_payload("grant"), headers=headers)
        assert resp.status_code == 201
        entry = client.get(
            f"/api/v1/journal-entries/{resp.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"102", "403"}

    def test_revenue_funding_posts_to_revenue(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/funding", json=_funding_payload("revenue"), headers=headers)
        assert resp.status_code == 201
        entry = client.get(
            f"/api/v1/journal-entries/{resp.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"102", "401"}

    def test_cash_method_posts_to_cash(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/funding", json=_funding_payload("investment", method="cash"), headers=headers
        )
        assert resp.status_code == 201
        entry = client.get(
            f"/api/v1/journal-entries/{resp.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert "101" in codes

    def test_loan_maturity_before_date_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/funding",
            json=_funding_payload("loan", maturity_date="2026-08-01"),
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "loan_maturity_invalid"

    def test_list_and_detail(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        client.post("/api/v1/funding", json=_funding_payload("investment"), headers=headers)
        listed = client.get("/api/v1/funding", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        detail = client.get(f"/api/v1/funding/{listed.json()[0]['id']}", headers=headers)
        assert detail.status_code == 200
        assert client.get("/api/v1/funding/999999", headers=headers).status_code == 404

    def test_staff_cannot_create(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        staff, _ = auth_headers(Role.STAFF)
        resp = client.post("/api/v1/funding", json=_funding_payload("investment"), headers=staff)
        assert resp.status_code == 403

    def test_viewer_can_read(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        client.post("/api/v1/funding", json=_funding_payload("investment"), headers=acct)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/funding", headers=viewer)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestFundingMappingsApi:
    def test_default_mappings_listed(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.get("/api/v1/funding/mappings", headers=headers)
        assert resp.status_code == 200
        by_type = {m["funding_type"]: m["account_code"] for m in resp.json()}
        assert by_type == {
            "investment": "301",
            "loan": "205",
            "grant": "403",
            "revenue": "401",
        }

    def test_update_mapping_changes_posting(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.put(
            "/api/v1/funding/mappings/grant", json={"account_code": "403"}, headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["account_code"] == "403"

    def test_update_mapping_unknown_account(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.put(
            "/api/v1/funding/mappings/grant", json={"account_code": "999"}, headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_missing"

    def test_staff_cannot_update_mapping(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        staff, _ = auth_headers(Role.STAFF)
        resp = client.put(
            "/api/v1/funding/mappings/grant", json={"account_code": "403"}, headers=staff
        )
        assert resp.status_code == 403
