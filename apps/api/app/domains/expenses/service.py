"""Expenses service: lifecycle (draft → posted → voided) + posting rules.

Posting rule for an expense:
    Dr  <expense/account>      amount
    Cr  101 صندوق (cash)  OR  102 بانک (bank/online)
The whole flow (create draft → post → journal) happens inside one DB
transaction; posting is idempotent via idempotency_key + status guard.
Void creates a ledger reversal and marks the expense voided.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.jalali import entry_period
from app.domains.expenses.models import Attachment, Expense, ExpenseStatus, PaymentMethod
from app.domains.expenses.schemas import AttachmentOut, ExpenseOut
from app.domains.ledger.service import (
    create_draft_entry,
    get_account,
    next_reference,
    post_entry,
    void_entry,
)

logger = logging.getLogger(__name__)

ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "application/pdf"}

# Magic-byte signatures checked against the first bytes of the uploaded file.
# A client-declared content-type alone is never trusted (it is trivially
# spoofable) — the signature must match one of the allowed formats.
_MAGIC_SIGNATURES: dict[str, list[tuple[bytes, int]]] = {
    "image/jpeg": [(b"\xff\xd8\xff", 3)],
    "image/png": [(b"\x89PNG\r\n\x1a\n", 8)],
    "application/pdf": [(b"%PDF-", 5)],
}


def sniff_content_type(data: bytes) -> str | None:
    """Detect the real format from the file's magic bytes; None if unknown."""
    for content_type, signatures in _MAGIC_SIGNATURES.items():
        for magic, offset in signatures:
            if data[:offset] == magic:
                return content_type
    return None


class ExpenseError(AppError):
    def __init__(self, message: str, code: str = "expense_error", status_code: int = 422) -> None:
        super().__init__(message, code=code, status_code=status_code)


def _payment_account(method: PaymentMethod) -> str:
    """Which cash/bank account the payment comes out of."""
    return "101" if method == PaymentMethod.CASH else "102"


def _to_out(db: Session, expense: Expense) -> ExpenseOut:
    from app.domains.ledger.models import Account

    acct = db.get(Account, expense.account_id)
    return ExpenseOut(
        id=expense.id,
        number=expense.number,
        entry_date=expense.entry_date,
        contact_id=expense.contact_id,
        project_id=expense.project_id,
        account_code=acct.code if acct else "?",
        account_name=acct.name if acct else "?",
        amount=expense.amount,
        payment_method=expense.payment_method,
        reference=expense.reference,
        description=expense.description,
        notes=expense.notes,
        status=expense.status,
        journal_entry_id=expense.journal_entry_id,
        created_at=expense.created_at,
        posted_at=expense.posted_at,
        attachments=[AttachmentOut.model_validate(a) for a in expense.attachments],
    )


def create_expense(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    entry_date: dt.date,
    account_code: str,
    amount: int,
    description: str,
    payment_method: PaymentMethod,
    contact_id: int | None,
    project_id: int | None,
    reference: str | None,
    notes: str | None,
    idempotency_key: str | None,
) -> Expense:
    if idempotency_key:
        existing = db.scalar(
            select(Expense).where(
                Expense.company_id == company_id,
                Expense.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
    account = get_account(db, company_id, account_code)
    if account is None:
        raise ExpenseError(f"حساب با کد {account_code} یافت نشد", code="account_missing")
    if not account.is_active:
        raise ExpenseError(f"حساب {account_code} غیرفعال است", code="account_inactive")
    if contact_id is not None:
        from app.domains.contacts.service import get_contact

        if get_contact(db, company_id, contact_id) is None:
            raise ExpenseError("طرف‌حساب یافت نشد", code="contact_missing", status_code=404)
    if project_id is not None:
        from app.domains.projects.service import get_project

        if get_project(db, company_id, project_id) is None:
            raise ExpenseError("پروژه یافت نشد", code="project_missing", status_code=404)

    expense = Expense(
        company_id=company_id,
        entry_date=entry_date,
        contact_id=contact_id,
        project_id=project_id,
        account_id=account.id,
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        description=description.strip(),
        notes=notes,
        status=ExpenseStatus.DRAFT,
        created_by_id=actor_id,
        idempotency_key=idempotency_key,
    )
    db.add(expense)
    db.flush()
    # number assigned on first post (keeps drafts numbered-free until posted)
    logger.info("expense draft created", extra={"expense_id": expense.id, "by": actor_id})
    return expense


def post_expense(db: Session, company_id: int, expense_id: int, actor_id: int) -> Expense:
    expense = db.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.company_id == company_id)
    )
    if expense is None:
        raise ExpenseError("هزینه یافت نشد", code="expense_missing", status_code=404)
    if expense.status == ExpenseStatus.POSTED:
        if expense.idempotency_key:
            return expense  # idempotent replay
        raise ExpenseError("هزینه از قبل ثبت شده است", code="expense_already_posted")
    if expense.status == ExpenseStatus.VOIDED:
        raise ExpenseError("هزینه برگشت خورده است", code="expense_voided")

    from app.domains.ledger.models import Account

    acct = db.get(Account, expense.account_id)
    if acct is None:
        raise ExpenseError("حساب مرتبط یافت نشد", code="account_missing")
    year, month = entry_period(expense.entry_date)
    entry = create_draft_entry(
        db,
        company_id=expense.company_id,
        actor_id=actor_id,
        entry_date=expense.entry_date,
        memo=f"هزینه: {expense.description}",
        lines=[
            (acct.code, expense.amount, 0),
            (_payment_account(expense.payment_method), 0, expense.amount),
        ],
        idempotency_key=None,  # ledger draft is internal; expense carries the key
    )
    posted = post_entry(db, company_id, entry.id, actor_id)
    expense.number = next_reference(db, expense.company_id, year, month, "EXP")
    expense.status = ExpenseStatus.POSTED
    expense.journal_entry_id = posted.id
    expense.posted_at = dt.datetime.now(dt.UTC)
    db.flush()
    logger.info(
        "expense posted",
        extra={"expense_id": expense.id, "number": expense.number, "entry_id": posted.id},
    )
    return expense


def void_expense(
    db: Session,
    company_id: int,
    expense_id: int,
    actor_id: int,
    memo: str | None = None,
) -> Expense:
    expense = db.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.company_id == company_id)
    )
    if expense is None:
        raise ExpenseError("هزینه یافت نشد", code="expense_missing", status_code=404)
    if expense.status != ExpenseStatus.POSTED:
        raise ExpenseError("فقط هزینه ثبت‌شده را می‌توان برگشت زد", code="expense_not_posted")
    if expense.journal_entry_id is None:
        raise ExpenseError("سند مرتبط یافت نشد", code="expense_no_entry")
    reversal = void_entry(db, company_id, expense.journal_entry_id, actor_id, memo=memo)
    expense.status = ExpenseStatus.VOIDED
    db.flush()
    logger.info("expense voided", extra={"expense_id": expense.id, "reversal_entry": reversal.id})
    return expense


def list_expenses(db: Session, company_id: int) -> list[Expense]:
    return list(
        db.scalars(
            select(Expense)
            .where(Expense.company_id == company_id)
            .order_by(Expense.entry_date.desc(), Expense.id.desc())
        )
    )


def get_expense(db: Session, company_id: int, expense_id: int) -> Expense | None:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.company_id != company_id:
        return None
    return expense


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------


def media_root() -> Path:
    settings = get_settings()
    return Path(settings.media_dir)


def validate_upload(content_type: str, size_bytes: int, filename: str, data: bytes) -> None:
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise ExpenseError(
            "فرمت فایل مجاز نیست؛ فقط تصویر (JPG/PNG) یا PDF بپذیرید",
            code="upload_type",
            status_code=415,
        )
    if size_bytes <= 0 or size_bytes > get_settings().max_upload_bytes:
        raise ExpenseError(
            "حجم فایل باید حداکثر ۵ مگابایت باشد", code="upload_size", status_code=413
        )
    if len(filename) > 255:
        raise ExpenseError("نام فایل بیش از حد طولانی است", code="upload_name")
    # The declared content-type is not trusted: the file's magic bytes must
    # match an allowed format (prevents HTML/JS disguised as an image/PDF).
    if sniff_content_type(data) != content_type:
        raise ExpenseError(
            "محتوای فایل با نوع اعلامشده همخوانی ندارد",
            code="upload_content_mismatch",
            status_code=415,
        )


def store_attachment(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    owner_type: str,
    owner_id: int,
    filename: str,
    content_type: str,
    data: bytes,
) -> Attachment:
    validate_upload(content_type, len(data), filename, data)
    root = media_root()
    root.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower()[:10]
    storage_key = f"{owner_type}/{owner_id}/{uuid.uuid4().hex}{ext}"
    target = root / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    attachment = Attachment(
        company_id=company_id,
        owner_type=owner_type,
        owner_id=owner_id,
        filename=filename[:255],
        content_type=content_type,
        size_bytes=len(data),
        storage_key=storage_key,
        uploaded_by_id=actor_id,
    )
    db.add(attachment)
    db.flush()
    logger.info("attachment stored", extra={"attachment_id": attachment.id, "key": storage_key})
    return attachment


def get_attachment(db: Session, company_id: int, attachment_id: int) -> Attachment | None:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None or attachment.company_id != company_id:
        return None
    return attachment


def read_attachment_file(attachment: Attachment) -> bytes | None:
    target = media_root() / attachment.storage_key
    try:
        return target.read_bytes()
    except FileNotFoundError:
        return None
