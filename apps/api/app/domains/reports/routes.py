"""Report API routes (read-only; all roles including viewer).

All figures are derived server-side from the posted ledger — clients can
never inject raw SQL or totals. Date parameters are ISO Gregorian dates;
the UI converts Solar Hijri inputs (docs: docs/accounting-rules.md).
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.db import get_db
from app.domains.identity.models import User
from app.domains.reports.service import (
    aging,
    balance_sheet,
    budget_vs_actual,
    cash_flow,
    dashboard,
    funding_summary,
    general_ledger,
    profit_loss,
    reconciliation,
    trial_balance,
)

router = APIRouter(tags=["reports"])

_RANGE_MSG = "تاریخ شروع نمی‌تواند بعد از پایان باشد"


def _invalid_range() -> JSONResponse:
    return JSONResponse(
        {"error": {"code": "invalid_range", "message": _RANGE_MSG}},
        status_code=422,
    )


@router.get("/reports/dashboard")
def reports_dashboard(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, object]:
    return dashboard(db, user.company_id)


@router.get("/reports/trial-balance")
def reports_trial_balance(
    as_of: dt.date | None = Query(default=None, description="ISO date; defaults to today"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return trial_balance(db, user.company_id, as_of or dt.date.today())


@router.get("/reports/balance-sheet")
def reports_balance_sheet(
    as_of: dt.date | None = Query(default=None, description="ISO date; defaults to today"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return balance_sheet(db, user.company_id, as_of or dt.date.today())


@router.get("/reports/profit-loss", response_model=None)
def reports_profit_loss(
    from_date: dt.date = Query(alias="from"),
    to_date: dt.date = Query(alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    if from_date > to_date:
        return _invalid_range()
    return profit_loss(db, user.company_id, from_date, to_date)


@router.get("/reports/cash-flow", response_model=None)
def reports_cash_flow(
    from_date: dt.date = Query(alias="from"),
    to_date: dt.date = Query(alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    if from_date > to_date:
        return _invalid_range()
    return cash_flow(db, user.company_id, from_date, to_date)


@router.get("/reports/general-ledger", response_model=None)
def reports_general_ledger(
    account_code: str = Query(min_length=1, max_length=20),
    from_date: dt.date = Query(alias="from"),
    to_date: dt.date = Query(alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    if from_date > to_date:
        return _invalid_range()
    result = general_ledger(db, user.company_id, account_code, from_date, to_date)
    if "error" in result:
        return JSONResponse(
            {"error": {"code": "account_not_found", "message": "حساب یافت نشد"}},
            status_code=404,
        )
    return result


@router.get("/reports/aging")
def reports_aging(
    as_of: dt.date | None = Query(default=None, description="ISO date; defaults to today"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return aging(db, user.company_id, as_of or dt.date.today())


@router.get("/reports/budget-vs-actual", response_model=None)
def reports_budget_vs_actual(
    from_date: dt.date = Query(alias="from"),
    to_date: dt.date = Query(alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    if from_date > to_date:
        return _invalid_range()
    return budget_vs_actual(db, user.company_id, from_date, to_date)


@router.get("/reports/funding-summary", response_model=None)
def reports_funding_summary(
    from_date: dt.date = Query(alias="from"),
    to_date: dt.date = Query(alias="to"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object] | JSONResponse:
    if from_date > to_date:
        return _invalid_range()
    return funding_summary(db, user.company_id, from_date, to_date)


@router.get("/reports/reconciliation")
def reports_reconciliation(
    as_of: dt.date | None = Query(default=None, description="ISO date; defaults to today"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return reconciliation(db, user.company_id, as_of or dt.date.today())
