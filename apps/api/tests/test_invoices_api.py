"""Service + API tests: invoice lifecycle, payments, PDF, RBAC."""

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


def _customer(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/v1/contacts", json={"name": "مشتری خلیجفارس", "roles": ["customer"]}, headers=headers
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _invoice_payload(customer_id: int, **overrides) -> dict:
    payload: dict = {
        "customer_id": customer_id,
        "issue_date": ISSUE,
        "due_date": DUE,
        "items": [
            {
                "description": "دستگاه خنککننده C-200",
                "quantity": 2,
                "unit_price": 2_500_000,
                "discount": 0,
            },
            {"description": "خدمات نصب", "quantity": 1, "unit_price": 1_500_000, "discount": 0},
        ],
        "payment_instructions": "انتقال به حساب بانک ملت",
    }
    payload.update(overrides)
    return payload


class TestInvoiceLifecycleApi:
    def test_create_invoice_computes_totals(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        resp = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["total"] == 6_500_000  # 2*2.5M + 1.5M
        assert len(body["items"]) == 2
        assert body["balance"] == 6_500_000

    def test_discount_applied(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        resp = client.post(
            "/api/v1/invoices",
            json=_invoice_payload(
                cid,
                items=[
                    {
                        "description": "کالا",
                        "quantity": 1,
                        "unit_price": 10_000_000,
                        "discount": 1_000_000,
                    }
                ],
            ),
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["total"] == 9_000_000

    def test_due_before_issue_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        resp = client.post(
            "/api/v1/invoices",
            json=_invoice_payload(cid, due_date="2026-08-01"),
            headers=headers,
        )
        assert resp.status_code == 422

    def test_issue_posts_receivable_and_revenue(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        issued = client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        assert issued.status_code == 200
        body = issued.json()
        assert body["status"] == "issued"
        assert body["number"] == "INV-1405-0001"
        assert body["journal_entry_id"] is not None

        entry = client.get(
            f"/api/v1/journal-entries/{body['journal_entry_id']}", headers=headers
        ).json()
        debit = sum(ln["debit"] for ln in entry["lines"])
        credit = sum(ln["credit"] for ln in entry["lines"])
        assert debit == credit == 6_500_000
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"203", "401"}

    def test_double_issue_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        resp = client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_already_issued"

    def test_partial_payment_then_full(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)

        # partial 2M cash
        p1 = client.post(
            f"/api/v1/invoices/{inv['id']}/payments",
            json={"amount": 2_000_000, "paid_at": "2026-08-15", "method": "cash"},
            headers=headers,
        )
        assert p1.status_code == 201
        detail = client.get(f"/api/v1/invoices/{inv['id']}", headers=headers).json()
        assert detail["status"] == "partially_paid"
        assert detail["paid_total"] == 2_000_000
        assert detail["balance"] == 4_500_000

        # payment entry: Dr 101 / Cr 203
        entry = client.get(
            f"/api/v1/journal-entries/{p1.json()['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert codes == {"101", "203"}

        # rest via bank
        client.post(
            f"/api/v1/invoices/{inv['id']}/payments",
            json={"amount": 4_500_000, "paid_at": "2026-08-20", "method": "bank"},
            headers=headers,
        )
        detail = client.get(f"/api/v1/invoices/{inv['id']}", headers=headers).json()
        assert detail["status"] == "paid"
        assert detail["balance"] == 0

    def test_overpayment_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post(
            "/api/v1/invoices",
            json=_invoice_payload(
                cid, items=[{"description": "x", "quantity": 1, "unit_price": 1_000_000}]
            ),
            headers=headers,
        ).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        resp = client.post(
            f"/api/v1/invoices/{inv['id']}/payments",
            json={"amount": 2_000_000, "paid_at": "2026-08-15", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_overpayment"

    def test_void_without_payments_reverses(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        issued = client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers).json()
        voided = client.post(f"/api/v1/invoices/{inv['id']}/void", headers=headers)
        assert voided.status_code == 200
        assert voided.json()["status"] == "void"

        entries = client.get("/api/v1/journal-entries", headers=headers).json()
        reversals = [e for e in entries if e["reversal_of_id"] == issued["journal_entry_id"]]
        assert len(reversals) == 1

    def test_void_with_payments_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        client.post(
            f"/api/v1/invoices/{inv['id']}/payments",
            json={"amount": 1_000_000, "paid_at": "2026-08-15", "method": "cash"},
            headers=headers,
        )
        resp = client.post(f"/api/v1/invoices/{inv['id']}/void", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_has_payments"

    def test_overdue_derived(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post(
            "/api/v1/invoices",
            json=_invoice_payload(cid, issue_date="2026-07-01", due_date="2026-07-15"),
            headers=headers,
        ).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        detail = client.get(f"/api/v1/invoices/{inv['id']}", headers=headers).json()
        assert detail["is_overdue"] is True

    def test_staff_cannot_create_or_issue(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, acct)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=acct).json()
        staff, _ = auth_headers(Role.STAFF)
        assert (
            client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=staff).status_code
            == 403
        )
        assert client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=staff).status_code == 403

    def test_viewer_can_read(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, acct)
        client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=acct)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/invoices", headers=viewer)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestInvoicePdfApi:
    def test_pdf_download(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
        resp = client.get(f"/api/v1/invoices/{inv['id']}/pdf", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"
        assert len(resp.content) > 500

    def test_pdf_requires_auth(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        resp = client.get(f"/api/v1/invoices/{inv['id']}/pdf")
        assert resp.status_code == 401


class TestInvoiceErrorPaths:
    def test_payment_on_draft_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        resp = client.post(
            f"/api/v1/invoices/{inv['id']}/payments",
            json={"amount": 100_000, "paid_at": "2026-08-15", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_not_issued"

    def test_payment_on_missing_invoice(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/invoices/999999/payments",
            json={"amount": 100_000, "paid_at": "2026-08-15", "method": "cash"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_void_never_issued(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        resp = client.post(f"/api/v1/invoices/{inv['id']}/void", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "void"

    def test_void_twice_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        inv = client.post("/api/v1/invoices", json=_invoice_payload(cid), headers=headers).json()
        client.post(f"/api/v1/invoices/{inv['id']}/void", headers=headers)
        resp = client.post(f"/api/v1/invoices/{inv['id']}/void", headers=headers)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_already_voided"

    def test_line_total_zero_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        resp = client.post(
            "/api/v1/invoices",
            json=_invoice_payload(
                cid,
                items=[{"description": "x", "quantity": 1, "unit_price": 5_000, "discount": 5_000}],
            ),
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invoice_line_invalid"

    def test_detail_missing(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.get("/api/v1/invoices/999999", headers=headers)
        assert resp.status_code == 404
