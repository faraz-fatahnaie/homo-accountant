# mypy: disable-error-code="type-arg,arg-type,index,no-any-return,operator,union-attr,attr-defined"
"""Ready-made query templates (plain-Persian, nontechnical users)."""

from __future__ import annotations

import datetime as dt

from app.core.jalali import jalali_to_gregorian


def _quarter_start(year: int, month: int) -> dt.date:
    """Start of the Solar Hijri quarter containing (year, month)."""
    q = (month - 1) // 3
    start_month = q * 3 + 1
    return jalali_to_gregorian(year, start_month, 1)


def _today() -> dt.date:
    from app.core.jalali import gregorian_to_jalali

    jy, jm, _ = gregorian_to_jalali(dt.date.today())
    return jalali_to_gregorian(jy, jm, 1)  # first of current month


def build_templates() -> list[dict[str, object]]:
    today = dt.date.today()
    jy, jm, _ = __import__("app.core.jalali", fromlist=["gregorian_to_jalali"]).gregorian_to_jalali(
        today
    )
    quarter_start = _quarter_start(jy, jm)
    return [
        {
            "id": "invoices_overdue",
            "name": "فاکتورهای فروش معوق",
            "description": "صورت‌حساب‌های صادرشده یا جزئی پرداخت‌شده که سررسیدشان گذشته است",
            "ast": {
                "dataset": "invoices",
                "fields": ["number", "customer_name", "issue_date", "due_date", "total", "status"],
                "filters": [
                    {"field": "status", "op": "in", "value": ["issued", "partially_paid"]},
                    {"field": "due_date", "op": "lt", "value": today.isoformat()},
                ],
                "sorts": [{"field": "due_date", "dir": "asc"}],
                "page": 1,
                "page_size": 25,
            },
        },
        {
            "id": "bills_unpaid_over",
            "name": "فاکتورهای خرید پرداختنشده بالای X در سه ماه گذشته",
            "description": "فاکتورهای خرید باز یا جزئی پرداخت‌شده با مبلغ بیشتر از X "
            "در سه ماه گذشته",
            "ast": {
                "dataset": "bills",
                "fields": ["number", "vendor_name", "issue_date", "due_date", "total", "status"],
                "filters": [
                    {"field": "status", "op": "in", "value": ["open", "partially_paid"]},
                    {"field": "total", "op": "gt", "value": 0},
                    {"field": "issue_date", "op": "gte", "value": quarter_start.isoformat()},
                ],
                "sorts": [{"field": "due_date", "dir": "asc"}],
                "page": 1,
                "page_size": 25,
            },
        },
        {
            "id": "expenses_by_project",
            "name": "هزینه‌های ثبت‌شده به تفکیک پروژه",
            "description": "مجموع هزینه‌های ثبت‌شده هر پروژه (در سال جاری)",
            "ast": {
                "dataset": "expenses",
                "fields": ["project_name", "amount"],
                "filters": [
                    {"field": "status", "op": "eq", "value": "posted"},
                ],
                "aggregations": [
                    {"function": "sum", "field": "amount", "groups": ["project_name"]}
                ],
                "sorts": [{"field": "project_name", "dir": "asc"}],
                "page": 1,
                "page_size": 50,
            },
        },
        {
            "id": "funding_summary",
            "name": "خلاصه تأمین مالی",
            "description": "مجموع مبالغ تأمین مالی به تفکیک نوع (سرمایه، وام، کمک، درآمد)",
            "ast": {
                "dataset": "funding",
                "fields": ["funding_type", "amount"],
                "aggregations": [
                    {"function": "sum", "field": "amount", "groups": ["funding_type"]}
                ],
                "sorts": [{"field": "funding_type", "dir": "asc"}],
                "page": 1,
                "page_size": 25,
            },
        },
    ]
