"""Service + API tests: bills (payables) lifecycle, payments, RBAC."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts

ISSUE = dt.date(2026, 8, 10).isoformat()
DUE = dt.date(2026, 9, 10).isoformat()


def _seed(client: TestClient, db) -> None:
    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    get_period(db, company.id, 1405, 5)
    get_period(db, company.id, 1405, 6)
    db.commit()


def _vendor(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/v1/contacts", json={"name": "فولاد البرز", "roles": ["vendor"]}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _bill_payload(vendor_id: int, **overrides) -> dict:
    payload: dict = {
        "vendor_id": vendor_id,
        "account_code": "603",
        "issue_date": ISSUE,
        "due_date": DUE,
        "bill_number": "F-88712",
        "memo": "خرید ورق فولادی ۲ تن",
        "total": 48_500_000,
    }
    payload.update(overrides)
    return payload


class TestBillLifecycleApi:
    def test_create_bill_draft(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        resp = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["total"] == 48_500_000
        assert body["vendor_name"] == "فولاد البرز"

    def test_post_bill_posts_payable(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        posted = client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        assert posted.status_code == 200
        body = posted.json()
        assert body["status"] == "open"
        assert body["number"] == "BIL-1405-0001"
        assert body["journal_entry_id"] is not None

        entry = client.get(
            f"/api/v1/journal-entries/{body['journal_entry_id']}", headers=headers
        ).json()
        debit = sum(ln["debit"] for ln in entry["lines"])
        credit = sum(ln["credit"] for ln in entry["lines"])
        assert debit == credit == 48_500_000
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"603", "204"}  # Dr expense / Cr payable

    def test_partial_then_full_payment(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)

        p1 = client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"amount": 20_000_000, "paid_at": "2026-08-20", "method": "bank"},
            headers=headers,
        )
        assert p1.status_code == 201
        detail = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()
        assert detail["status"] == "partially_paid"
        assert detail["paid_total"] == 20_000_000
        assert detail["balance"] == 28_500_000

        # payment entry: Dr 204 / Cr 102 (bank)
        entry = client.get(
            f"/api/v1/journal-entries/{p1.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"204", "102"}

        client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"amount": 28_500_000, "paid_at": "2026-08-25", "method": "cash"},
            headers=headers,
        )
        detail = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()
        assert detail["status"] == "paid"
        assert detail["balance"] == 0

    def test_overpayment_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post(
            "/api/v1/bills", json=_bill_payload(vid, total=1_000_000), headers=headers
        ).json()
        client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        resp = client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"amount": 2_000_000, "paid_at": "2026-08-20", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "bill_overpayment"

    def test_void_reverses(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        posted = client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers).json()
        voided = client.post(f"/api/v1/bills/{bill['id']}/void", headers=headers)
        assert voided.status_code == 200
        assert voided.json()["status"] == "void"
        entries = client.get("/api/v1/journal-entries", headers=headers).json()
        reversals = [e for e in entries if e["reversal_of_id"] == posted["journal_entry_id"]]
        assert len(reversals) == 1

    def test_void_with_payments_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"amount": 1_000_000, "paid_at": "2026-08-20", "method": "cash"},
            headers=headers,
        )
        resp = client.post(f"/api/v1/bills/{bill['id']}/void", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "bill_has_payments"

    def test_double_post_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        resp = client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "bill_already_posted"

    def test_overdue_derived(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post(
            "/api/v1/bills",
            json=_bill_payload(vid, issue_date="2026-07-01", due_date="2026-07-15"),
            headers=headers,
        ).json()
        client.post(f"/api/v1/bills/{bill['id']}/post", headers=headers)
        detail = client.get(f"/api/v1/bills/{bill['id']}", headers=headers).json()
        assert detail["is_overdue"] is True

    def test_staff_cannot_create_or_post(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, acct)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=acct).json()
        staff, _ = auth_headers(Role.STAFF)
        assert (
            client.post("/api/v1/bills", json=_bill_payload(vid), headers=staff).status_code == 403
        )
        assert client.post(f"/api/v1/bills/{bill['id']}/post", headers=staff).status_code == 403

    def test_viewer_can_read(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, acct)
        client.post("/api/v1/bills", json=_bill_payload(vid), headers=acct)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/bills", headers=viewer)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_unknown_account_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        resp = client.post(
            "/api/v1/bills", json=_bill_payload(vid, account_code="999"), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_missing"

    def test_missing_bill_404(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        assert client.post("/api/v1/bills/999999/post", headers=headers).status_code == 404
        assert client.get("/api/v1/bills/999999", headers=headers).status_code == 404


class TestBillErrorPaths:
    def test_void_never_posted(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        resp = client.post(f"/api/v1/bills/{bill['id']}/void", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "void"

    def test_void_twice_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        client.post(f"/api/v1/bills/{bill['id']}/void", headers=headers)
        resp = client.post(f"/api/v1/bills/{bill['id']}/void", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "bill_already_voided"

    def test_payment_on_draft_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        bill = client.post("/api/v1/bills", json=_bill_payload(vid), headers=headers).json()
        resp = client.post(
            f"/api/v1/bills/{bill['id']}/payments",
            json={"amount": 100_000, "paid_at": "2026-08-20", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "bill_not_posted"

    def test_due_before_issue_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        vid = _vendor(client, headers)
        resp = client.post(
            "/api/v1/bills", json=_bill_payload(vid, due_date="2026-08-01"), headers=headers
        )
        assert resp.status_code == 422

    def test_inactive_account_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post(
            "/api/v1/accounts",
            json={"code": "608", "name": "هزینه تست خرید", "type": "expense"},
            headers=headers,
        ).json()
        client.patch(
            f"/api/v1/accounts/{created['id']}", json={"is_active": False}, headers=headers
        )
        vid = _vendor(client, headers)
        resp = client.post(
            "/api/v1/bills", json=_bill_payload(vid, account_code="608"), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_inactive"

    def test_payment_missing_bill_404(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/bills/999999/payments",
            json={"amount": 100_000, "paid_at": "2026-08-20", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 404
