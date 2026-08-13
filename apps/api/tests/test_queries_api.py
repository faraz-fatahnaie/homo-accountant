"""Service + API tests: query builder (allowlist, injection, exports, saved)."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts


def _seed(client: TestClient, db) -> None:
    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()


def _customer(client: TestClient, headers: dict) -> int:
    resp = client.post(
        "/api/v1/contacts", json={"name": "مشتری تست", "roles": ["customer"]}, headers=headers
    )
    return resp.json()["id"]


def _make_invoice(client: TestClient, headers: dict, customer_id: int, total: int) -> int:
    inv = client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": "2026-08-01",
            "due_date": "2026-09-01",
            "items": [{"description": "کالا", "quantity": 1, "unit_price": total}],
        },
        headers=headers,
    ).json()
    client.post(f"/api/v1/invoices/{inv['id']}/issue", headers=headers)
    return inv["id"]


def _run(client: TestClient, headers: dict, ast: dict):
    return client.post("/api/v1/query-builder/run", json=ast, headers=headers)


class TestQueryRunApi:
    def test_run_invoices_query(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        _make_invoice(client, headers, cid, 6_500_000)
        ast = {
            "dataset": "invoices",
            "fields": ["number", "customer_name", "total", "status"],
            "filters": [{"field": "status", "op": "eq", "value": "issued"}],
            "sorts": [{"field": "total", "dir": "desc"}],
            "page": 1,
            "page_size": 10,
        }
        resp = _run(client, headers, ast)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert len(body["rows"]) == 1
        assert body["rows"][0][1] == "مشتری تست"  # customer_name joined
        labels = [c["label"] for c in body["columns"]]
        assert "مشتری" in labels

    def test_unknown_dataset_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = _run(client, headers, {"dataset": "secret_table", "fields": ["*"]})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "dataset_invalid"

    def test_unknown_field_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = _run(
            client,
            headers,
            {"dataset": "invoices", "fields": ["password"], "page": 1, "page_size": 10},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "field_invalid"

    def test_sql_injection_string_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        # any attempt to smuggle raw SQL fails at validation (no such field/op)
        ast = {
            "dataset": "invoices",
            "fields": ["number"],
            "filters": [{"field": "number; DROP TABLE invoices", "op": "eq", "value": "x"}],
            "page": 1,
            "page_size": 10,
        }
        resp = _run(client, headers, ast)
        assert resp.status_code == 422
        # also a bogus operator
        ast2 = {
            "dataset": "invoices",
            "fields": ["number"],
            "filters": [{"field": "number", "op": ";;--", "value": "x"}],
            "page": 1,
            "page_size": 10,
        }
        resp2 = _run(client, headers, ast2)
        assert resp2.status_code == 422
        assert resp2.json()["error"]["code"] == "filter_op_invalid"

    def test_company_scope(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        acct, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, acct)
        _make_invoice(client, acct, cid, 1_000_000)
        # viewer in the same company sees the same rows (single company MVP)
        viewer, _ = auth_headers(Role.VIEWER)
        resp = _run(
            client,
            viewer,
            {"dataset": "invoices", "fields": ["number"], "page": 1, "page_size": 10},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_aggregation_sum_by_group(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        cid = _customer(client, headers)
        _make_invoice(client, headers, cid, 5_000_000)
        _make_invoice(client, headers, cid, 3_000_000)
        ast = {
            "dataset": "invoices",
            "fields": ["status", "total"],
            "aggregations": [{"function": "sum", "field": "total", "groups": ["status"]}],
            "page": 1,
            "page_size": 10,
        }
        resp = _run(client, headers, ast)
        assert resp.status_code == 200
        body = resp.json()
        assert body["aggregated"] is True
        assert len(body["rows"]) == 1  # all issued
        assert 8_000_000 in body["rows"][0]  # sum present

    def test_sum_only_on_amount_field(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = _run(
            client,
            headers,
            {
                "dataset": "invoices",
                "fields": ["number"],
                "aggregations": [{"function": "sum", "field": "number"}],
                "page": 1,
                "page_size": 10,
            },
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "agg_field_invalid"

    def test_pagination_limits(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = _run(
            client,
            headers,
            {"dataset": "invoices", "fields": ["number"], "page": 1, "page_size": 9999},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "page_size_invalid"

    def test_templates_and_summarize(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        templates = client.get("/api/v1/query-builder/templates", headers=headers)
        assert templates.status_code == 200
        assert len(templates.json()) >= 4
        tpl = templates.json()[0]
        summary = client.post("/api/v1/query-builder/summarize", json=tpl["ast"], headers=headers)
        assert summary.status_code == 200
        assert "مجموعه داده" in summary.json()["summary"]


class TestQueryExportApi:
    def _with_data(self, client: TestClient, headers: dict) -> dict:
        cid = _customer(client, headers)
        _make_invoice(client, headers, cid, 6_500_000)
        return {
            "dataset": "invoices",
            "fields": ["number", "customer_name", "total"],
            "page": 1,
            "page_size": 10,
        }

    def test_csv_export_and_formula_protection(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        ast = self._with_data(client, headers)
        resp = client.post("/api/v1/query-builder/export?format=csv", json=ast, headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        text = resp.content.decode("utf-8-sig")
        assert "مشتری" in text  # header label
        assert "6,500,000" in text or "6500000" in text

        # formula injection: a cell starting with = gets a ' prefix
        from app.domains.queries.export import _safe

        assert _safe("=SUM(A1)") == "'=SUM(A1)"
        assert _safe("+1+1") == "'+1+1"
        assert _safe("سلام") == "سلام"

    def test_xlsx_export(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        ast = self._with_data(client, headers)
        resp = client.post("/api/v1/query-builder/export?format=xlsx", json=ast, headers=headers)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.headers["content-type"]
        # validate it's a real xlsx
        assert zipfile.is_zipfile(io.BytesIO(resp.content))

    def test_export_invalid_format(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.post(
            "/api/v1/query-builder/export?format=pdf",
            json={"dataset": "invoices", "fields": ["number"], "page": 1, "page_size": 10},
            headers=headers,
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "format_invalid"


class TestSavedQueriesApi:
    def test_save_list_duplicate_delete(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        ast = {"dataset": "invoices", "fields": ["number", "total"], "page": 1, "page_size": 25}
        created = client.post(
            "/api/v1/query-builder/saved",
            json={"name": "فاکتورهای من", "dataset": "invoices", "ast": ast},
            headers=headers,
        )
        assert created.status_code == 201
        qid = created.json()["id"]

        listed = client.get("/api/v1/query-builder/saved", headers=headers)
        assert listed.status_code == 200
        assert any(q["name"] == "فاکتورهای من" for q in listed.json())

        dup = client.post(f"/api/v1/query-builder/saved/{qid}/duplicate", headers=headers)
        assert dup.status_code == 201
        assert dup.json()["name"] == "فاکتورهای من (کپی)"

        resp = client.delete(f"/api/v1/query-builder/saved/{qid}", headers=headers)
        assert resp.status_code == 204

    def test_save_invalid_ast_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.post(
            "/api/v1/query-builder/saved",
            json={
                "name": "بد",
                "dataset": "invoices",
                "ast": {"dataset": "invoices", "fields": ["nope"]},
            },
            headers=headers,
        )
        assert resp.status_code == 422

    def test_delete_missing_404(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.delete("/api/v1/query-builder/saved/999999", headers=headers)
        assert resp.status_code == 404
