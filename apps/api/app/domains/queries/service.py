"""Query-builder service: AST validation → compiled, parameterized SQL.

Safety model:
- dataset, fields, filters, sorts, aggregations are resolved ONLY against the
  allowlist (datasets.py). Unknown names raise QueryError. No raw SQL is ever
  accepted — the compiler builds SQLAlchemy expressions from the allowlist.
- Every query is scoped to the caller's company.
- Filters are parameterized (values bound, never interpolated).
- Complexity limits: filters ≤ 20 nodes, depth ≤ 3, page_size ≤ 200,
  fields ≤ 30, export rows ≤ 5000.
- A statement timeout is set on the connection before each run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.domains.queries.datasets import DATASETS, DatasetDef, column_for

logger = logging.getLogger(__name__)

MAX_FILTERS = 20
MAX_DEPTH = 3
MAX_FIELDS = 30
MAX_PAGE_SIZE = 200
MAX_EXPORT_ROWS = 5000
STATEMENT_TIMEOUT_MS = 15000

OPS: dict[str, object] = {
    "eq": lambda c, v: c == v,
    "ne": lambda c, v: c != v,
    "gt": lambda c, v: c > v,
    "gte": lambda c, v: c >= v,
    "lt": lambda c, v: c < v,
    "lte": lambda c, v: c <= v,
    "contains": lambda c, v: c.ilike(f"%{v}%"),
    "in": lambda c, v: c.in_(v),
    "is_null": lambda c, v: c.is_(None) if v else c.is_not(None),
}


class QueryError(Exception):
    def __init__(self, message: str, code: str = "query_error", status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


@dataclass
class CompiledQuery:
    columns: list  # list of (field, label, type, expr)
    stmt: object
    amount_fields: set[str]
    has_aggregation: bool
    group_fields: list[str]


def validate_ast(ast: dict) -> None:
    if not isinstance(ast, dict):
        raise QueryError("ساختار پرسوجو نامعتبر است", code="ast_invalid")
    dataset = ast.get("dataset")
    if dataset not in DATASETS:
        raise QueryError("مجموعه داده نامعتبر است", code="dataset_invalid")
    d: DatasetDef = DATASETS[dataset]

    fields = ast.get("fields", [])
    if not isinstance(fields, list) or not fields:
        raise QueryError("حداقل یک فیلد انتخاب کنید", code="fields_required")
    if len(fields) > MAX_FIELDS:
        raise QueryError("تعداد فیلدها بیش از حد مجاز است", code="fields_too_many")
    for f in fields:
        if f not in d.columns:
            raise QueryError(f"فیلد ناشناخته: {f}", code="field_invalid")

    sorts = ast.get("sorts", [])
    if not isinstance(sorts, list):
        raise QueryError("مرتبسازی نامعتبر است", code="sorts_invalid")
    for s in sorts:
        if s.get("field") not in d.columns:
            raise QueryError("فیلد مرتبسازی نامعتبر است", code="sort_field_invalid")
        if s.get("dir") not in ("asc", "desc"):
            raise QueryError("جهت مرتبسازی نامعتبر است", code="sort_dir_invalid")

    filters = ast.get("filters", [])
    _validate_filters(filters, d, depth=0)

    aggs = ast.get("aggregations", [])
    if not isinstance(aggs, list) or len(aggs) > 2:
        raise QueryError("تجمیع نامعتبر است", code="aggs_invalid")
    for a in aggs:
        if a.get("function") not in ("count", "sum"):
            raise QueryError("تابع تجمیع نامعتبر است", code="agg_function_invalid")
        if a.get("function") == "sum":
            fld = a.get("field")
            col = column_for(dataset, fld) if fld else None
            if col is None or not col.amount:
                raise QueryError("جمع فقط روی فیلدهای مبلغ مجاز است", code="agg_field_invalid")
        if "groups" in a:
            for g in a["groups"]:
                if g not in d.columns:
                    raise QueryError("فیلد گروهبندی نامعتبر است", code="agg_group_invalid")

    page = ast.get("page", 1)
    page_size = ast.get("page_size", 25)
    if not isinstance(page, int) or page < 1:
        raise QueryError("شماره صفحه نامعتبر است", code="page_invalid")
    if not isinstance(page_size, int) or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise QueryError("اندازه صفحه نامعتبر است", code="page_size_invalid")


def _validate_filters(node: object, d: DatasetDef, depth: int) -> None:
    if node is None or node == []:
        return
    if isinstance(node, list):  # top-level list = implicit AND
        if len(node) > MAX_FILTERS:
            raise QueryError("تعداد فیلترها بیش از حد مجاز است", code="filters_too_many")
        for child in node:
            _validate_filters(child, d, depth)
        return
    if depth > MAX_DEPTH:
        raise QueryError("عمق فیلترها بیش از حد مجاز است", code="filters_too_deep")
    if isinstance(node, dict) and "and" in node:
        children = node["and"]
        if len(children) > MAX_FILTERS:
            raise QueryError("تعداد فیلترها بیش از حد مجاز است", code="filters_too_many")
        for c in children:
            _validate_filters(c, d, depth + 1)
        return
    if isinstance(node, dict) and "or" in node:
        children = node["or"]
        if len(children) > MAX_FILTERS:
            raise QueryError("تعداد فیلترها بیش از حد مجاز است", code="filters_too_many")
        for c in children:
            _validate_filters(c, d, depth + 1)
        return
    if not isinstance(node, dict) or "field" not in node or "op" not in node:
        raise QueryError("ساختار فیلتر نامعتبر است", code="filter_invalid")
    field = node.get("field")
    if field not in d.columns:
        raise QueryError(f"فیلتر روی فیلد ناشناخته: {field}", code="filter_field_invalid")
    op = node.get("op")
    if op not in OPS:
        raise QueryError(f"عملگر نامعتبر: {op}", code="filter_op_invalid")
    if op == "in" and not isinstance(node.get("value"), list):
        raise QueryError("مقدار عملگر in باید فهرست باشد", code="filter_value_invalid")
    if op in ("is_null",) and not isinstance(node.get("value"), bool):
        raise QueryError("مقدار is_null باید درست/نادرست باشد", code="filter_value_invalid")


def _compile_filters(node: object, d: DatasetDef) -> object:
    if isinstance(node, list):  # implicit AND
        conds = [_compile_filters(c, d) for c in node]
        return and_(*conds) if len(conds) > 1 else conds[0]
    if isinstance(node, dict) and "and" in node:
        return and_(*[_compile_filters(c, d) for c in node["and"]])
    if isinstance(node, dict) and "or" in node:
        return or_(*[_compile_filters(c, d) for c in node["or"]])
    field_name = node["field"]
    col_def = d.columns[field_name]
    col = col_def.expr
    op = node["op"]
    value = node["value"]
    value = _coerce_value(value, col_def.type, op)
    if op == "contains":
        value = str(value)
    return OPS[op](col, value)


def compile_query(db: Session, company_id: int, ast: dict) -> CompiledQuery:
    validate_ast(ast)
    dataset = ast["dataset"]
    d = DATASETS[dataset]

    fields = ast["fields"]
    aggs = ast.get("aggregations", [])

    columns: list[tuple] = []
    amount_fields: set[str] = set()
    has_aggregation = bool(aggs)
    group_fields: list[str] = []

    selected: list = []
    if has_aggregation:
        for a in aggs:
            if a["function"] == "count":
                selected.append(func.count().label("count"))
                columns.append(("count", "تعداد", "amount", func.count()))
                amount_fields.add("count")
            else:
                fld = a["field"]
                col = d.columns[fld]
                selected.append(func.sum(col.expr).label(f"sum_{fld}"))
                columns.append((f"sum_{fld}", f"جمع {col.label}", "amount", func.sum(col.expr)))
                amount_fields.add(f"sum_{fld}")
        for g in aggs[0].get("groups", []):
            col = d.columns[g]
            selected.append(col.expr.label(g))
            columns.append((g, col.label, col.type, col.expr))
        group_fields = aggs[0].get("groups", [])
    else:
        for f in fields:
            col = d.columns[f]
            selected.append(col.expr.label(f))
            columns.append((f, col.label, col.type, col.expr))
            if col.amount:
                amount_fields.add(f)

    stmt = select(*selected).select_from(d.base).where(d.base.company_id == company_id)
    for selectable, onclause, is_outer in d.joins:
        stmt = stmt.outerjoin(selectable, onclause) if is_outer else stmt.join(selectable, onclause)

    # filters (top-level list combined with AND)
    filters = ast.get("filters", [])
    if filters:
        conds = [_compile_filters(f, d) for f in filters]
        stmt = stmt.where(conds[0] if len(conds) == 1 else and_(*conds))

    if has_aggregation:
        if group_fields:
            stmt = stmt.group_by(*[d.columns[g].expr for g in group_fields])
        else:
            stmt = stmt.group_by()
    else:
        for s in ast.get("sorts", []):
            expr = d.columns[s["field"]].expr
            stmt = stmt.order_by(expr.desc() if s["dir"] == "desc" else expr.asc())

    return CompiledQuery(
        columns=columns,
        stmt=stmt,
        amount_fields=amount_fields,
        has_aggregation=has_aggregation,
        group_fields=group_fields,
    )


def run_query(db: Session, company_id: int, ast: dict) -> dict:
    """Run a validated query; returns {columns, rows, total, page, page_size, has_more}."""
    compiled = compile_query(db, company_id, ast)
    page = ast.get("page", 1)
    page_size = ast.get("page_size", 25)

    # count total
    count_stmt = select(func.count()).select_from(compiled.stmt.subquery())
    _set_timeout(db)
    total = db.execute(count_stmt).scalar_one()

    data_stmt = compiled.stmt.limit(page_size).offset((page - 1) * page_size)
    _set_timeout(db)
    result = db.execute(data_stmt)

    columns_meta = [{"field": c[0], "label": c[1], "type": c[2]} for c in compiled.columns]
    rows = [[_jsonable(v) for v in row] for row in result.all()]

    return {
        "columns": columns_meta,
        "rows": rows,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "has_more": page * page_size < int(total),
        "aggregated": compiled.has_aggregation,
    }


def _jsonable(value: object) -> object:
    import datetime as _dt
    from decimal import Decimal

    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    return value


def _coerce_value(value: object, col_type: str, op: str) -> object:
    import datetime as _dt

    if op == "is_null":
        return bool(value)
    if col_type == "date":
        if isinstance(value, list):
            return [_dt.date.fromisoformat(str(v)) for v in value]
        try:
            return _dt.date.fromisoformat(str(value))
        except ValueError:
            raise QueryError("مقدار تاریخ نامعتبر است", code="filter_value_invalid") from None
    if col_type == "amount":
        if isinstance(value, list):
            return [int(v) for v in value]
        return int(value)
    if col_type == "bool":
        return bool(value)
    return value


def _set_timeout(db: Session) -> None:
    try:
        db.connection().exec_driver_sql(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}")
    except Exception:  # noqa: BLE001,S110 — best-effort guard
        logger.debug("statement_timeout not set", exc_info=True)


# ---------------------------------------------------------------------------
# plain-language summary
# ---------------------------------------------------------------------------

OP_LABELS = {
    "eq": "برابر با",
    "ne": "نامساوی با",
    "gt": "بزرگتر از",
    "gte": "بزرگتر یا مساوی",
    "lt": "کوچکتر از",
    "lte": "کوچکتر یا مساوی",
    "contains": "شامل عبارت",
    "in": "در فهرست",
    "is_null": "خالی باشد",
}
TYPE_LABELS = {
    "string": "متن",
    "date": "تاریخ",
    "amount": "مبلغ",
    "enum": "گزینه",
    "bool": "بله/خیر",
}


def summarize_ast(ast: dict[str, object]) -> str:
    """A plain-Persian summary of the query (client + server use this)."""
    dataset = ast.get("dataset", "")
    d = DATASETS.get(dataset)
    parts = [f"مجموعه داده: {d.label if d else dataset}"]
    fields = ast.get("fields", [])
    if fields:
        parts.append(
            "فیلدها: "
            + "، ".join(
                column_for(dataset, f).label if column_for(dataset, f) else f for f in fields
            )
        )
    aggs = ast.get("aggregations", [])
    if aggs:
        parts.append("تجمیع: " + "، ".join(_agg_summary(a, dataset) for a in aggs))
    filters = ast.get("filters", [])
    if filters:
        parts.append("شرط: " + _filter_summary(filters, dataset))
    sorts = ast.get("sorts", [])
    if sorts:
        parts.append("مرتبسازی: " + "، ".join(_sort_summary(s, dataset) for s in sorts))
    return " — ".join(parts)


def _sort_summary(s: dict[str, object], dataset: str) -> str:
    col = column_for(dataset, s.get("field", ""))
    label = col.label if col else s.get("field", "")
    return f"{label} ({'صعودی' if s.get('dir') == 'asc' else 'نزولی'})"


def _agg_summary(a: dict[str, object], dataset: str) -> str:
    if a.get("function") == "count":
        return "تعداد ردیفها"
    fld = a.get("field", "")
    col = column_for(dataset, fld)
    groups = a.get("groups", [])
    g = (
        " بر اساس "
        + "، ".join(column_for(dataset, x).label if column_for(dataset, x) else x for x in groups)
        if groups
        else ""
    )
    return f"جمع {col.label if col else fld}{g}"


def _filter_summary(nodes: object, dataset: str) -> str:
    if isinstance(nodes, list):
        return " و ".join(_filter_summary(n, dataset) for n in nodes)
    if isinstance(nodes, dict) and "and" in nodes:
        return "(" + " و ".join(_filter_summary(c, dataset) for c in nodes["and"]) + ")"
    if isinstance(nodes, dict) and "or" in nodes:
        return "(" + " یا ".join(_filter_summary(c, dataset) for c in nodes["or"]) + ")"
    col = column_for(dataset, nodes.get("field", ""))
    label = col.label if col else nodes.get("field", "")
    op = OP_LABELS.get(nodes.get("op", ""), nodes.get("op", ""))
    val = nodes.get("value")
    if nodes.get("op") == "is_null":
        return f"{label} {'خالی باشد' if val else 'خالی نباشد'}"
    return f"{label} {op} {val}"
