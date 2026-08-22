"""Expenses API routes (incl. attachment upload/download)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.config import get_settings
from app.core.db import get_db
from app.core.http import attachment_disposition
from app.domains.expenses.schemas import AttachmentOut, ExpenseCreate, ExpenseOut, ExpenseUpdate
from app.domains.expenses.service import (
    ExpenseError,
    create_expense,
    get_attachment,
    get_expense,
    list_expenses,
    post_expense,
    read_attachment_file,
    store_attachment,
    void_expense,
)
from app.domains.identity.models import Role, User

router = APIRouter(tags=["expenses"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)
POSTERS = (Role.OWNER, Role.ACCOUNTANT)
# Staff may create drafts / submit records; only accountant+ owner post or void.
DRAFTERS = (Role.OWNER, Role.ACCOUNTANT, Role.STAFF)


def _handle(exc: ExpenseError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@router.get("/expenses", response_model=list[ExpenseOut])
def expenses_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[ExpenseOut]:
    from app.domains.expenses.service import _to_out

    return [_to_out(db, e) for e in list_expenses(db, user.company_id)]


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def expenses_create(
    payload: ExpenseCreate,
    actor: User = Depends(require_roles(*DRAFTERS)),
    db: Session = Depends(get_db),
) -> ExpenseOut | JSONResponse:
    from app.domains.expenses.service import _to_out

    try:
        expense = create_expense(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            entry_date=payload.entry_date,
            account_code=payload.account_code,
            amount=payload.amount,
            description=payload.description,
            payment_method=payload.payment_method,
            contact_id=payload.contact_id,
            project_id=payload.project_id,
            reference=payload.reference,
            notes=payload.notes,
            idempotency_key=payload.idempotency_key,
        )
    except ExpenseError as exc:
        return _handle(exc)
    db.commit()
    return _to_out(db, expense)


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
def expenses_update(
    expense_id: int,
    payload: ExpenseUpdate,
    actor: User = Depends(require_roles(*DRAFTERS)),
    db: Session = Depends(get_db),
) -> ExpenseOut | JSONResponse:
    from app.domains.expenses.service import _to_out

    expense = get_expense(db, actor.company_id, expense_id)
    if expense is None:
        return error_response(404, "not_found", "هزینه یافت نشد")
    if expense.status != "draft":
        return error_response(422, "expense_not_draft", "فقط هزینه پیش‌نویس قابل ویرایش است")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(expense, key, value)
    db.commit()
    return _to_out(db, expense)


@router.get("/expenses/{expense_id}", response_model=ExpenseOut)
def expenses_detail(
    expense_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ExpenseOut | JSONResponse:
    from app.domains.expenses.service import _to_out

    expense = get_expense(db, user.company_id, expense_id)
    if expense is None:
        return error_response(404, "not_found", "هزینه یافت نشد")
    return _to_out(db, expense)


@router.post("/expenses/{expense_id}/post", response_model=ExpenseOut)
def expenses_post(
    expense_id: int,
    actor: User = Depends(require_roles(*POSTERS)),
    db: Session = Depends(get_db),
) -> ExpenseOut | JSONResponse:
    from app.domains.expenses.service import _to_out

    try:
        expense = post_expense(db, actor.company_id, expense_id, actor.id)
    except ExpenseError as exc:
        db.rollback()
        return _handle(exc)
    except Exception:  # ledger errors (unbalanced etc.) surface as 422
        db.rollback()
        raise
    db.commit()
    return _to_out(db, expense)


@router.post("/expenses/{expense_id}/void", response_model=ExpenseOut)
def expenses_void(
    expense_id: int,
    actor: User = Depends(require_roles(*POSTERS)),
    db: Session = Depends(get_db),
) -> ExpenseOut | JSONResponse:
    from app.domains.expenses.service import _to_out

    try:
        expense = void_expense(db, actor.company_id, expense_id, actor.id)
    except ExpenseError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, expense)


# --------------------------------------------------------------------------
# Attachments
# --------------------------------------------------------------------------


@router.post(
    "/expenses/{expense_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def expenses_attach(
    expense_id: int,
    file: UploadFile = File(...),
    actor: User = Depends(require_roles(*DRAFTERS)),
    db: Session = Depends(get_db),
) -> AttachmentOut | JSONResponse:
    expense = get_expense(db, actor.company_id, expense_id)
    if expense is None:
        return error_response(404, "not_found", "هزینه یافت نشد")
    if expense.status != "draft":
        return error_response(
            422, "expense_not_draft", "فقط به هزینه پیش‌نویس می‌توان پیوست اضافه کرد"
        )
    try:
        data = await file.read(get_settings().max_upload_bytes + 1)
    finally:
        await file.close()
    try:
        attachment = store_attachment(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            owner_type="expense",
            owner_id=expense.id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            data=data,
        )
    except ExpenseError as exc:
        return _handle(exc)
    db.commit()
    return AttachmentOut.model_validate(attachment)


@router.get("/attachments/{attachment_id}", response_model=None)
def attachment_download(
    attachment_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    attachment = get_attachment(db, user.company_id, attachment_id)
    if attachment is None:
        return error_response(404, "not_found", "پیوست یافت نشد")
    data = read_attachment_file(attachment)
    if data is None:
        return error_response(404, "not_found", "فایل پیوست موجود نیست")
    return Response(
        content=data,
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": attachment_disposition(attachment.filename),
            "X-Content-Type-Options": "nosniff",
        },
    )
