"""API tests (slice 8): dashboard KPIs, financial reports, drill-downs, reconciliation.

Every assertion checks a figure against the posted ledger — reports must never
drift from the journal. Scenarios build a small but complete ledger:
owner investment, an expense, a customer invoice with partial payment, a
supplier bill, and a funding event.
"""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.domains.identity.models import Role
from app.domains.identity.service import ensure_default_company
from app.domains.ledger.service import get_period, seed_chart_of_accounts

D1 = dt.date(2026, 8, 1).isoformat()  # 1405/05/10
D2 = dt.date(2026, 8, 13).isoformat()  # 1405/05/22
AS_OF = "2026-08-13"

EXPENSE_AMOUNT = 48_500_000
INVEST_AMOUNT = 400_000_000
INVOICE_TOTAL = 133_000_000
INVOICE_PAID = 50_000_000
LOAN_AMOUNT = 100_000_000


def _seed(client: TestClient, db, with_funding: bool = False) -> None:
    from app.domains.funding.service import ensure_default_mappings

    company = ensure_default_company(db)
    seed_chart_of_accounts(db, company.id)
    if with_funding:
        ensure_default_mappings(db, company.id)
    get_period(db, company.id, 1405, 5)
    db.commit()


def _contact(client: TestClient, headers: dict, name: str, role: str) -> int:
    resp = client.post(
        "/api/v1/contacts",
        json={"name": name, "roles": [role]},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _journal(client: TestClient, headers: dict, entry_date: str, memo: str, lines: list) -> dict:
    created = client.post(
        "/api/v1/journal-entries",
        json={"entry_date": entry_date, "memo": memo, "lines": lines},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    posted = client.post(f"/api/v1/journal-entries/{created.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    return posted.json()


def _expense(client: TestClient, headers: dict, **overrides: object) -> dict:
    payload: dict = {
        "entry_date": D2,
        "account_code": "603",
        "amount": EXPENSE_AMOUNT,
        "payment_method": "bank",
        "description": "هزینه مواد اولیه",
    }
    payload.update(overrides)
    created = client.post("/api/v1/expenses", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    posted = client.post(f"/api/v1/expenses/{created.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    return posted.json()


def _invoice(
    client: TestClient, headers: dict, customer_id: int, *, due_date: str, issue_date: str = D1
) -> dict:
    created = client.post(
        "/api/v1/invoices",
        json={
            "customer_id": customer_id,
            "issue_date": issue_date,
            "due_date": due_date,
            "items": [{"description": "فروش کالا", "quantity": 1, "unit_price": INVOICE_TOTAL}],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    issued = client.post(f"/api/v1/invoices/{created.json()['id']}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    return issued.json()


def _bill(
    client: TestClient, headers: dict, vendor_id: int, *, due_date: str, issue_date: str = D1
) -> dict:
    created = client.post(
        "/api/v1/bills",
        json={
            "vendor_id": vendor_id,
            "account_code": "603",
            "issue_date": issue_date,
            "due_date": due_date,
            "memo": "فاکتور خرید",
            "total": 30_000_000,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    posted = client.post(f"/api/v1/bills/{created.json()['id']}/post", headers=headers)
    assert posted.status_code == 200, posted.text
    return posted.json()


def _build_ledger(client: TestClient, headers: dict, with_funding: bool = False) -> None:
    """Post the canonical slice-8 scenario ledger."""
    _journal(
        client,
        headers,
        D1,
        "سرمایهگذاری مالک",
        [
            {"account_code": "102", "debit": INVEST_AMOUNT, "credit": 0},
            {"account_code": "301", "debit": 0, "credit": INVEST_AMOUNT},
        ],
    )
    _expense(client, headers)
    customer = _contact(client, headers, "شرکت مشتری", "customer")
    overdue = _invoice(
        client, headers, customer, issue_date="2026-06-15", due_date="2026-07-01"
    )  # 43 days overdue on AS_OF
    _invoice(client, headers, customer, due_date="2026-09-01")  # future
    # partial payment against the overdue invoice
    pay = client.post(
        f"/api/v1/invoices/{overdue['id']}/payments",
        json={
            "amount": INVOICE_PAID,
            "paid_at": D2,
            "method": "bank",
            "reference": "پرداخت نقدی",
        },
        headers=headers,
    )
    assert pay.status_code == 201, pay.text
    vendor = _contact(client, headers, "تأمینکننده صنعت", "vendor")
    _bill(
        client, headers, vendor, issue_date="2025-12-01", due_date="2026-01-01"
    )  # >90 days overdue on AS_OF
    if with_funding:
        investor = _contact(client, headers, "سرمایهگذار", "investor")
        client.post(
            "/api/v1/funding",
            json={
                "funding_type": "investment",
                "event_date": D1,
                "amount": 50_000_000,
                "method": "bank",
                "contact_id": investor,
            },
            headers=headers,
        )
        client.post(
            "/api/v1/funding",
            json={
                "funding_type": "loan",
                "event_date": D1,
                "amount": LOAN_AMOUNT,
                "method": "bank",
                "contact_id": vendor,
                "maturity_date": "2027-08-01",
            },
            headers=headers,
        )


class TestEmptyLedger:
    """All reports must be zeroed and 'reconciled' on an empty ledger."""

    def test_reports_on_empty_ledger(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)

        tb = client.get(f"/api/v1/reports/trial-balance?as_of={AS_OF}", headers=headers).json()
        assert tb["balanced"] is True and tb["total_debit"] == 0

        bs = client.get(f"/api/v1/reports/balance-sheet?as_of={AS_OF}", headers=headers).json()
        assert bs["total_assets"] == 0 and bs["reconciled"] is True

        pl = client.get(f"/api/v1/reports/profit-loss?from={D1}&to={D2}", headers=headers).json()
        assert pl["total_revenue"] == 0 and pl["net_income"] == 0

        cf = client.get(f"/api/v1/reports/cash-flow?from={D1}&to={D2}", headers=headers).json()
        assert cf["beginning_cash_bank"] == 0 and cf["ending_cash_bank"] == 0
        assert cf["reconciled"] is True

        ag = client.get(f"/api/v1/reports/aging?as_of={AS_OF}", headers=headers).json()
        assert ag["receivable"]["total"] == 0 and ag["payable"]["total"] == 0
        assert ag["reconciled"] is True

        dash = client.get("/api/v1/reports/dashboard", headers=headers).json()
        assert dash["cash_bank"] == 0 and dash["revenue"] == 0 and dash["net_income"] == 0

        rec = client.get(f"/api/v1/reports/reconciliation?as_of={AS_OF}", headers=headers).json()
        assert rec["all_ok"] is True


class TestTrialBalance:
    def test_totals_balance_and_signed_rows(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        resp = client.get(f"/api/v1/reports/trial-balance?as_of={AS_OF}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["balanced"] is True
        assert body["total_debit"] == body["total_credit"] > 0
        by_code = {r["code"]: r for r in body["rows"]}
        # expense 603 debit-positive (expense + supplier bill)
        assert by_code["603"]["balance"] == EXPENSE_AMOUNT + 30_000_000
        # bank 102 debit-negative (credited); supplier bill has no cash effect
        assert by_code["102"]["balance"] == INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT
        # receivable 203 = invoices − payments (asset → debit-positive)
        assert by_code["203"]["balance"] == 2 * INVOICE_TOTAL - INVOICE_PAID
        # payable 204 = supplier bill (liability → credit-positive)
        assert by_code["204"]["balance"] == 30_000_000

    def test_drafts_excluded(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        # a draft only — never posted
        created = client.post(
            "/api/v1/journal-entries",
            json={
                "entry_date": D2,
                "memo": "پیشنویس",
                "lines": [
                    {"account_code": "603", "debit": 10_000_000, "credit": 0},
                    {"account_code": "102", "debit": 0, "credit": 10_000_000},
                ],
            },
            headers=headers,
        )
        assert created.status_code == 201

        tb = client.get(f"/api/v1/reports/trial-balance?as_of={AS_OF}", headers=headers).json()
        assert tb["total_debit"] == 0

    def test_as_of_filters_entries(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        before = client.get(
            "/api/v1/reports/trial-balance?as_of=2025-11-30", headers=headers
        ).json()
        assert before["total_debit"] == 0  # nothing posted before the earliest entry


class TestBalanceSheet:
    def test_assets_equal_liab_plus_equity(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(f"/api/v1/reports/balance-sheet?as_of={AS_OF}", headers=headers).json()
        assert body["reconciled"] is True
        assert body["total_assets"] == body["total_liabilities_equity"]

        # assets = 102 (bank) + 203 (receivable); equity 301 + current income
        expected_assets = (
            INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT + (2 * INVOICE_TOTAL - INVOICE_PAID) - 0
        )  # bills post Dr 603 expense / Cr 204 payable (no cash effect)
        assert body["total_assets"] == expected_assets
        assert body["net_income"] == 2 * INVOICE_TOTAL - EXPENSE_AMOUNT - 30_000_000
        # payable 204 sits in liabilities
        pay = next(a for a in body["liabilities"] if a["code"] == "204")
        assert pay["amount"] == 30_000_000

    def test_income_folded_into_equity(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(f"/api/v1/reports/balance-sheet?as_of={AS_OF}", headers=headers).json()
        equity_codes = {e["code"] for e in body["equity"]}
        assert "PNL" in equity_codes
        assert "301" in equity_codes
        assert body["total_equity"] == INVEST_AMOUNT + body["net_income"]


class TestProfitLoss:
    def test_revenue_expenses_net(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(
            "/api/v1/reports/profit-loss?from=2025-12-01&to=2026-08-13", headers=headers
        ).json()
        assert body["total_revenue"] == 2 * INVOICE_TOTAL
        assert body["total_expenses"] == EXPENSE_AMOUNT + 30_000_000
        assert body["net_income"] == 2 * INVOICE_TOTAL - EXPENSE_AMOUNT - 30_000_000
        revenue_codes = {r["code"] for r in body["revenue"]}
        expense_codes = {e["code"] for e in body["expenses"]}
        assert "401" in revenue_codes and "603" in expense_codes

    def test_range_filters(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        # only the expense is on D2
        body = client.get(
            "/api/v1/reports/profit-loss?from=2026-08-13&to=2026-08-13", headers=headers
        ).json()
        assert body["total_revenue"] == 0
        assert body["total_expenses"] == EXPENSE_AMOUNT
        assert body["net_income"] == -EXPENSE_AMOUNT


class TestCashFlow:
    def test_direct_method_sections_reconcile(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(f"/api/v1/reports/cash-flow?from={D1}&to={D2}", headers=headers).json()
        assert body["reconciled"] is True
        # operating: invoice partial payment (+50M) and bank expense (−48.5M) = +1.5M
        assert body["sections"]["operating"]["net"] == INVOICE_PAID - EXPENSE_AMOUNT
        # financing: owner investment
        assert body["sections"]["financing"]["net"] == INVEST_AMOUNT
        # investing + other untouched
        assert body["sections"]["investing"]["net"] == 0
        assert body["sections"]["other"]["net"] == 0
        assert body["beginning_cash_bank"] == 0
        assert body["ending_cash_bank"] == INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT
        assert body["net_change"] == body["ending_cash_bank"]

    def test_beginning_balance_carries_prior_cash(
        self, client: TestClient, db, auth_headers
    ) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        # window starts after the investment → beginning = 400M
        body = client.get(
            "/api/v1/reports/cash-flow?from=2026-08-05&to=2026-08-13", headers=headers
        ).json()
        assert body["beginning_cash_bank"] == INVEST_AMOUNT
        assert body["ending_cash_bank"] == INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT
        assert body["reconciled"] is True


class TestGeneralLedger:
    def test_running_balance_and_closing(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(
            f"/api/v1/reports/general-ledger?account_code=102&from={D1}&to={D2}",
            headers=headers,
        ).json()
        assert body["account"]["code"] == "102"
        assert body["opening_balance"] == 0
        assert body["closing_balance"] == INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT
        # running balance on the last line equals the closing balance
        assert body["lines"][-1]["balance"] == body["closing_balance"]

    def test_unknown_account_404(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        resp = client.get(
            f"/api/v1/reports/general-ledger?account_code=999&from={D1}&to={D2}",
            headers=headers,
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "account_not_found"


class TestAging:
    def test_buckets_and_ledger_reconciliation(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers)

        body = client.get(f"/api/v1/reports/aging?as_of={AS_OF}", headers=headers).json()
        rec = body["receivable"]
        assert rec["total"] == 2 * INVOICE_TOTAL - INVOICE_PAID  # 216M
        assert rec["reconciled"] is True
        assert rec["ledger_balance"] == rec["total"]

        bucket_map = {b["key"]: b["amount"] for b in rec["buckets"]}
        # overdue invoice (due 2026-07-01, 43 days) partially paid → 31_60;
        # future invoice (due 2026-09-01) unpaid → current
        assert bucket_map["31_60"] == INVOICE_TOTAL - INVOICE_PAID
        assert bucket_map["current"] == INVOICE_TOTAL
        assert bucket_map["over_90"] == 0

        pay = body["payable"]
        assert pay["total"] == 30_000_000
        assert pay["reconciled"] is True
        pay_bucket = {b["key"]: b["amount"] for b in pay["buckets"]}
        assert pay_bucket["over_90"] == 30_000_000  # due 2026-01-01


class TestBudgetVsActual:
    def test_project_budget_utilization(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        proj = client.post(
            "/api/v1/projects",
            json={"name": "پروژه تولید", "status": "active", "budget": 200_000_000},
            headers=headers,
        )
        assert proj.status_code == 201
        _build_ledger(client, headers)  # expense has no project
        # allocate a posted expense to the project
        _expense(client, headers, project_id=proj.json()["id"])

        body = client.get(
            f"/api/v1/reports/budget-vs-actual?from={D1}&to={D2}", headers=headers
        ).json()
        row = next(r for r in body["rows"] if r["project_id"] == proj.json()["id"])
        assert row["budget"] == 200_000_000
        assert row["actual"] == EXPENSE_AMOUNT
        assert row["remaining"] == 200_000_000 - EXPENSE_AMOUNT
        assert row["utilization"] == round(EXPENSE_AMOUNT / 200_000_000, 4)
        assert body["total_budget"] == 200_000_000

    def test_expense_outside_range_excluded(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        proj = client.post(
            "/api/v1/projects",
            json={"name": "پروژه", "budget": 100_000_000},
            headers=headers,
        ).json()
        _expense(client, headers, project_id=proj["id"], entry_date="2026-07-01")

        body = client.get(
            "/api/v1/reports/budget-vs-actual?from=2026-08-01&to=2026-08-13", headers=headers
        ).json()
        row = next(r for r in body["rows"] if r["project_id"] == proj["id"])
        assert row["actual"] == 0


class TestFundingSummary:
    def test_events_reconcile_to_ledger_credits(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db, with_funding=True)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers, with_funding=True)

        body = client.get(
            f"/api/v1/reports/funding-summary?from={D1}&to={D2}", headers=headers
        ).json()
        assert body["reconciled"] is True
        by_type = {t["funding_type"]: t for t in body["types"]}
        # only funding EVENTS count (the 400M manual owner journal is not an event)
        assert by_type["investment"]["total"] == 50_000_000
        assert by_type["investment"]["ledger_credit"] == 50_000_000
        assert by_type["investment"]["reconciled"] is True
        assert by_type["loan"]["total"] == LOAN_AMOUNT
        assert by_type["loan"]["account_code"] == "205"
        assert by_type["loan"]["reconciled"] is True
        assert body["total"] == 50_000_000 + LOAN_AMOUNT


class TestDashboard:
    def test_kpis_match_reports(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db, with_funding=True)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers, with_funding=True)

        dash = client.get("/api/v1/reports/dashboard", headers=headers).json()
        assert dash["fiscal_year"] == 1405
        assert dash["cash_bank"] == INVEST_AMOUNT + INVOICE_PAID - EXPENSE_AMOUNT + 150_000_000
        assert dash["receivables"] == 2 * INVOICE_TOTAL - INVOICE_PAID
        assert dash["payables"] == 30_000_000
        assert dash["revenue"] == 2 * INVOICE_TOTAL
        # the supplier bill belongs to fiscal year 1404 → excluded from 1405 YTD
        assert dash["expenses"] == EXPENSE_AMOUNT
        assert dash["net_income"] == 2 * INVOICE_TOTAL - EXPENSE_AMOUNT
        assert dash["funding_total"] == 50_000_000 + LOAN_AMOUNT
        assert dash["funding_reconciled"] is True
        assert dash["aging_reconciled"] is True
        assert dash["cash_flow_reconciled"] is True
        assert len(dash["recent_entries"]) >= 3
        assert len(dash["key_accounts"]) > 0


class TestReconciliation:
    def test_consistent_ledger_all_checks_pass(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db, with_funding=True)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        _build_ledger(client, headers, with_funding=True)

        body = client.get(f"/api/v1/reports/reconciliation?as_of={AS_OF}", headers=headers).json()
        assert body["all_ok"] is True
        keys = {c["key"] for c in body["checks"]}
        assert keys == {
            "trial_balance",
            "balance_sheet",
            "cash_flow",
            "aging_receivable",
            "aging_payable",
            "funding",
            "profit_loss",
        }

    def test_irregular_ledger_flags_checks(self, client: TestClient, db, auth_headers) -> None:
        """A receivable that the ledger doesn't match must flag the check."""
        _seed(client, db)
        headers, _ = auth_headers(Role.ACCOUNTANT)
        # invoice posted (203 debit 100M) but then manually reversed via a
        # journal without touching the invoice → aging vs ledger mismatch
        customer = _contact(client, headers, "مشتری", "customer")
        invoice = client.post(
            "/api/v1/invoices",
            json={
                "customer_id": customer,
                "issue_date": "2026-06-01",
                "due_date": "2026-07-01",
                "items": [{"description": "فروش", "quantity": 1, "unit_price": 100_000_000}],
            },
            headers=headers,
        ).json()
        client.post(f"/api/v1/invoices/{invoice['id']}/issue", headers=headers)
        # manual journal credits 203 with 40M (as if a payment) — no InvoicePayment row
        _journal(
            client,
            headers,
            D2,
            "تسویه بخشی از دریافتنی (بدون ثبت پرداخت)",
            [
                {"account_code": "102", "debit": 40_000_000, "credit": 0},
                {"account_code": "203", "debit": 0, "credit": 40_000_000},
            ],
        )
        body = client.get(f"/api/v1/reports/reconciliation?as_of={AS_OF}", headers=headers).json()
        aging_check = next(c for c in body["checks"] if c["key"] == "aging_receivable")
        assert aging_check["ok"] is False
        assert body["all_ok"] is False


class TestAccessAndValidation:
    def test_viewer_can_read_all_reports(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        for path in (
            "/api/v1/reports/dashboard",
            f"/api/v1/reports/trial-balance?as_of={AS_OF}",
            f"/api/v1/reports/balance-sheet?as_of={AS_OF}",
            f"/api/v1/reports/profit-loss?from={D1}&to={D2}",
            f"/api/v1/reports/cash-flow?from={D1}&to={D2}",
            f"/api/v1/reports/aging?as_of={AS_OF}",
            f"/api/v1/reports/budget-vs-actual?from={D1}&to={D2}",
            f"/api/v1/reports/funding-summary?from={D1}&to={D2}",
            f"/api/v1/reports/reconciliation?as_of={AS_OF}",
        ):
            resp = client.get(path, headers=headers)
            assert resp.status_code == 200, (path, resp.text)

    def test_invalid_date_range_rejected(self, client: TestClient, db, auth_headers) -> None:
        _seed(client, db)
        headers, _ = auth_headers(Role.VIEWER)
        resp = client.get(
            "/api/v1/reports/profit-loss?from=2026-08-13&to=2026-08-01", headers=headers
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "invalid_range"
