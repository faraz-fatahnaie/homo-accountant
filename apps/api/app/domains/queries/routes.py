"""Query-builder API routes (read-only, allowlisted, no raw SQL)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.identity.models import User
from app.domains.queries.datasets import DATASETS
from app.domains.queries.export import to_csv_bytes, to_xlsx_bytes
from app.domains.queries.models import SavedQuery
from app.domains.queries.service import (
    MAX_EXPORT_ROWS,
    MAX_PAGE_SIZE,
    QueryError,
    run_query,
    summarize_ast,
    validate_ast,
)
from app.domains.queries.templates import build_templates

router = APIRouter(tags=["queries"])


class QueryRun(BaseModel):
    dataset: str
    fields: list[str] = Field(default_factory=list)
    filters: list[object] = Field(default_factory=list)
    sorts: list[object] = Field(default_factory=list)
    aggregations: list[object] = Field(default_factory=list)
    page: int = 1
    page_size: int = 25


class SavedQueryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dataset: str
    ast: dict


def _handle(exc: QueryError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@router.get("/query-builder/datasets")
def query_datasets(user: User = Depends(current_user)) -> list[dict[str, object]]:
    out = []
    for key, d in DATASETS.items():
        out.append(
            {
                "id": key,
                "label": d.label,
                "columns": [
                    {
                        "field": f,
                        "label": c.label,
                        "type": c.type,
                        "enum_options": c.enum_options,
                        "amount": c.amount,
                    }
                    for f, c in d.columns.items()
                ],
            }
        )
    return out


@router.get("/query-builder/templates")
def query_templates(user: User = Depends(current_user)) -> list[dict[str, object]]:
    return build_templates()


@router.post("/query-builder/run")
def query_run(
    payload: QueryRun, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> JSONResponse:
    ast: dict[str, object] = payload.model_dump()  # type: ignore[assignment]
    try:
        result = run_query(db, user.company_id, ast)
    except QueryError as exc:
        return _handle(exc)
    return JSONResponse(result)


@router.post("/query-builder/summarize")
def query_summarize(payload: QueryRun, user: User = Depends(current_user)) -> JSONResponse:
    try:
        validate_ast(payload.model_dump())
    except QueryError as exc:
        return _handle(exc)
    return JSONResponse({"summary": summarize_ast(payload.model_dump())})


@router.post("/query-builder/export", response_model=None)
def query_export(
    payload: QueryRun,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    format: str = "csv",
) -> Response | JSONResponse:
    ast: dict[str, object] = payload.model_dump()  # type: ignore[assignment]
    if format not in ("csv", "xlsx"):
        return error_response(422, "format_invalid", "فرمت خروجی باید csv یا xlsx باشد")
    try:
        validate_ast(ast)
    except QueryError as exc:
        return _handle(exc)
    # export up to MAX_EXPORT_ROWS across pages
    ast["page"] = 1
    ast["page_size"] = min(ast.get("page_size", 500), MAX_PAGE_SIZE)
    all_rows: list[list[object]] = []
    columns: list[dict[str, object]] = []
    page = 1
    while len(all_rows) < MAX_EXPORT_ROWS:
        run_ast = dict(ast)
        run_ast["page"] = page
        result = run_query(db, user.company_id, run_ast)
        columns = result["columns"]
        rows = result["rows"]
        if not rows:
            break
        all_rows.extend(rows)
        if not result["has_more"]:
            break
        page += 1
    all_rows = all_rows[:MAX_EXPORT_ROWS]

    if format == "csv":
        data = to_csv_bytes(columns, all_rows)
        media = "text/csv; charset=utf-8"
        filename = "query.csv"
    else:
        data = to_xlsx_bytes(columns, all_rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "query.xlsx"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# saved queries (personal views)
# ---------------------------------------------------------------------------


@router.get("/query-builder/saved")
def saved_list(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    items = db.scalars(
        select(SavedQuery)
        .where(SavedQuery.company_id == user.company_id)
        .order_by(SavedQuery.created_at.desc())
    )
    return [
        {
            "id": q.id,
            "name": q.name,
            "dataset": q.dataset,
            "ast": q.ast,
            "summary": summarize_ast(q.ast),
            "created_at": q.created_at,
        }
        for q in items
    ]


@router.post("/query-builder/saved", status_code=status.HTTP_201_CREATED)
def saved_create(
    payload: SavedQueryCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> JSONResponse:
    try:
        validate_ast(payload.ast)
    except QueryError as exc:
        return _handle(exc)
    saved = SavedQuery(
        company_id=user.company_id,
        name=payload.name.strip(),
        dataset=payload.dataset,
        ast=payload.ast,
        created_by_id=user.id,
    )
    db.add(saved)
    db.commit()
    return JSONResponse({"id": saved.id, "name": saved.name}, status_code=201)


@router.post("/query-builder/saved/{query_id}/duplicate", status_code=status.HTTP_201_CREATED)
def saved_duplicate(
    query_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> JSONResponse:
    saved = db.get(SavedQuery, query_id)
    if saved is None or saved.company_id != user.company_id:
        return error_response(404, "not_found", "پرس‌وجوی ذخیره‌شده یافت نشد")
    clone = SavedQuery(
        company_id=user.company_id,
        name=f"{saved.name} (کپی)",
        dataset=saved.dataset,
        ast=saved.ast,
        created_by_id=user.id,
    )
    db.add(clone)
    db.commit()
    return JSONResponse({"id": clone.id, "name": clone.name}, status_code=201)


@router.delete(
    "/query-builder/saved/{query_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def saved_delete(
    query_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response | JSONResponse:
    saved = db.get(SavedQuery, query_id)
    if saved is None or saved.company_id != user.company_id:
        return error_response(404, "not_found", "پرس‌وجوی ذخیره‌شده یافت نشد")
    db.delete(saved)
    db.commit()
    return Response(status_code=204)
