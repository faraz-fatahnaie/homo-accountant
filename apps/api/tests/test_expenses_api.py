"""Service + API tests: expense lifecycle (posting, void, attachments, RBAC)."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts


def _seed(client: TestClient, db) -> None:
    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()


def _expense_payload(**overrides) -> dict:
    payload: dict = {
        "entry_date": "2026-08-13",
        "account_code": "603",
        "amount": 48_500_000,
        "payment_method": "bank",
        "description": "خرید ورق فولادی ۲ تن",
        "contact_id": None,
        "project_id": None,
    }
    payload.update(overrides)
    return payload


class TestExpenseLifecycleApi:
    def test_staff_can_create_draft(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.STAFF)
        resp = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "draft"
        assert body["amount"] == 48_500_000
        assert body["account_code"] == "603"

    def test_staff_cannot_post(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        staff_headers, _ = auth_headers(Role.STAFF)
        created = client.post(
            "/api/v1/expenses", json=_expense_payload(), headers=staff_headers
        ).json()
        resp = client.post(f"/api/v1/expenses/{created['id']}/post", headers=staff_headers)
        assert resp.status_code == 403

    def test_accountant_posts_and_journal_is_balanced(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        posted = client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers)
        assert posted.status_code == 200
        body = posted.json()
        assert body["status"] == "posted"
        assert body["number"] == "EXP-1405-0001"
        assert body["journal_entry_id"] is not None

        # the linked journal entry is balanced and visible in the ledger
        entry = client.get(
            f"/api/v1/journal-entries/{body['journal_entry_id']}", headers=headers
        ).json()
        assert entry["status"] == "posted"
        lines = entry["lines"]
        debit = sum(ln["debit"] for ln in lines)
        credit = sum(ln["credit"] for ln in lines)
        assert debit == credit == 48_500_000
        codes = {ln["account_code"] for ln in lines}
        assert "603" in codes and "102" in codes  # bank payment

    def test_cash_payment_posts_against_cash(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post(
            "/api/v1/expenses",
            json=_expense_payload(payment_method="cash"),
            headers=headers,
        ).json()
        posted = client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers).json()
        entry = client.get(
            f"/api/v1/journal-entries/{posted['journal_entry_id']}", headers=headers
        ).json()
        codes = {ln["account_code"] for ln in entry["lines"]}
        assert "101" in codes  # cash

    def test_double_post_second_returns_same(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post(
            "/api/v1/expenses", json=_expense_payload(idempotency_key="dup-1"), headers=headers
        ).json()
        client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers)
        again = client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers)
        assert again.status_code == 200
        # same expense, same journal entry (idempotent)
        assert again.json()["id"] == created["id"]
        assert again.json()["journal_entry_id"] is not None

    def test_void_creates_reversal_and_marks_voided(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        posted = client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers).json()
        voided = client.post(f"/api/v1/expenses/{created['id']}/void", headers=headers)
        assert voided.status_code == 200
        assert voided.json()["status"] == "voided"

        # reversal entry exists in the ledger
        entries = client.get("/api/v1/journal-entries", headers=headers).json()
        reversals = [e for e in entries if e["reversal_of_id"] == posted["journal_entry_id"]]
        assert len(reversals) == 1
        assert reversals[0]["status"] == "posted"

    def test_void_draft_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        resp = client.post(f"/api/v1/expenses/{created['id']}/void", headers=headers)
        assert resp.status_code == 422

    def test_unknown_account_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post(
            "/api/v1/expenses", json=_expense_payload(account_code="999"), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_missing"

    def test_viewer_can_read_expenses(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        client.post("/api/v1/expenses", json=_expense_payload(), headers=acct)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = client.get("/api/v1/expenses", headers=viewer)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestAttachmentsApi:
    def _upload(
        self, client: TestClient, headers: dict, expense_id: int, filename: str = "faktor.pdf"
    ):
        return client.post(
            f"/api/v1/expenses/{expense_id}/attachments",
            files={"file": (filename, io.BytesIO(b"%PDF-1.4 test content"), "application/pdf")},
            headers=headers,
        )

    def test_upload_and_download_attachment(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        resp = self._upload(client, headers, expense["id"])
        assert resp.status_code == 201
        att = resp.json()
        assert att["content_type"] == "application/pdf"
        assert att["filename"] == "faktor.pdf"

        dl = client.get(f"/api/v1/attachments/{att['id']}", headers=headers)
        assert dl.status_code == 200
        assert dl.content == b"%PDF-1.4 test content"

        # attachment shows on the expense
        detail = client.get(f"/api/v1/expenses/{expense['id']}", headers=headers).json()
        assert len(detail["attachments"]) == 1

    def test_rejects_disallowed_type(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        resp = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            files={"file": ("evil.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")},
            headers=headers,
        )
        assert resp.status_code == 415

    def test_rejects_oversized(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        big = b"0" * (6 * 1024 * 1024)
        resp = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
            headers=headers,
        )
        assert resp.status_code == 413

    def test_rejects_mismatched_content(self, client: TestClient, db, auth_headers) -> None:
        """HTML/script bytes declared as a PDF must be rejected (magic bytes)."""
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        resp = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            files={
                "file": (
                    "innocent.pdf",
                    io.BytesIO(b"<script>alert(1)</script>"),
                    "application/pdf",
                )
            },
            headers=headers,
        )
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "upload_content_mismatch"

    def test_accepts_sniffed_jpeg(self, client: TestClient, db, auth_headers) -> None:
        """A real JPEG signature with image/jpeg passes the sniff."""
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        resp = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            files={
                "file": (
                    "receipt.jpg",
                    io.BytesIO(b"\xff\xd8\xff\xe0" + b"0" * 64),
                    "image/jpeg",
                )
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "image/jpeg"

    def test_cannot_attach_to_posted_expense(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        client.post(f"/api/v1/expenses/{expense['id']}/post", headers=headers)
        resp = self._upload(client, headers, expense["id"])
        assert resp.status_code == 422

    def test_attachment_download_requires_auth(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        expense = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        att = self._upload(client, headers, expense["id"]).json()
        resp = client.get(f"/api/v1/attachments/{att['id']}")
        assert resp.status_code == 401


class TestExpenseErrorPaths:
    def test_post_missing_expense(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/expenses/999999/post", headers=headers)
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "expense_missing"

    def test_void_missing_expense(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/expenses/999999/void", headers=headers)
        assert resp.status_code == 404

    def test_inactive_account_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        # create a custom (non-system) account, then deactivate it
        created = client.post(
            "/api/v1/accounts",
            json={"code": "607", "name": "هزینه تست", "type": "expense"},
            headers=headers,
        ).json()
        assert created["code"] == "607"
        client.patch(
            f"/api/v1/accounts/{created['id']}", json={"is_active": False}, headers=headers
        )
        resp = client.post(
            "/api/v1/expenses", json=_expense_payload(account_code="607"), headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "account_inactive"

    def test_amount_must_be_positive(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.post("/api/v1/expenses", json=_expense_payload(amount=0), headers=headers)
        assert resp.status_code == 422

    def test_update_posted_expense_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        created = client.post("/api/v1/expenses", json=_expense_payload(), headers=headers).json()
        client.post(f"/api/v1/expenses/{created['id']}/post", headers=headers)
        resp = client.patch(
            f"/api/v1/expenses/{created['id']}", json={"description": "تغییر"}, headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "expense_not_draft"
