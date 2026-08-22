"""Invoices service: lifecycle + posting rules.

Issue:   Dr 203 حساب‌های دریافتنی   total    /   Cr 401 درآمد فروش   total
Payment: Dr 101 صندوق / 102 بانک    amount  /   Cr 203 دریافتنی      amount
Void:    reversal of the issue entry (only allowed when nothing was paid).
All flows are single-transaction and reuse the ledger posting service.
"""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.jalali import entry_period
from app.domains.invoices.models import Invoice, InvoiceItem, InvoicePayment, InvoiceStatus
from app.domains.ledger.service import (
    create_draft_entry,
    get_account,
    next_reference,
    post_entry,
    void_entry,
)

logger = logging.getLogger(__name__)

RECEIVABLE_ACCOUNT = "203"
REVENUE_ACCOUNT = "401"


class InvoiceError(AppError):
    def __init__(self, message: str, code: str = "invoice_error", status_code: int = 422) -> None:
        super().__init__(message, code=code, status_code=status_code)


def _line_total(item: InvoiceItem) -> int:
    return item.quantity * item.unit_price - item.discount


def create_invoice(
    db: Session,
    *,
    company_id: int,
    actor_id: int,
    customer_id: int,
    project_id: int | None,
    issue_date: dt.date,
    due_date: dt.date,
    items: list[dict[str, object]],
    notes: str | None,
    payment_instructions: str | None,
) -> Invoice:
    if due_date < issue_date:
        raise InvoiceError("سررسید نمی‌تواند قبل از تاریخ صدور باشد", code="invoice_dates_invalid")
    if project_id is not None:
        from app.domains.projects.service import get_project

        if get_project(db, company_id, project_id) is None:
            raise InvoiceError("پروژه یافت نشد", code="project_missing", status_code=404)
    invoice = Invoice(
        company_id=company_id,
        customer_id=customer_id,
        project_id=project_id,
        issue_date=issue_date,
        due_date=due_date,
        status=InvoiceStatus.DRAFT,
        notes=notes,
        payment_instructions=payment_instructions,
        created_by_id=actor_id,
    )
    total = 0
    for it in items:
        quantity = int(str(it["quantity"]))
        unit_price = int(str(it["unit_price"]))
        discount = int(str(it.get("discount", 0)))
        line_total = quantity * unit_price - discount
        if line_total <= 0:
            raise InvoiceError("مبلغ هر ردیف باید بیشتر از صفر باشد", code="invoice_line_invalid")
        total += line_total
        invoice.items.append(
            InvoiceItem(
                description=it["description"],
                quantity=quantity,
                unit_price=unit_price,
                discount=discount,
                line_total=line_total,
            )
        )
    invoice.total = total
    db.add(invoice)
    db.flush()
    logger.info("invoice draft created", extra={"invoice_id": invoice.id, "by": actor_id})
    return invoice


def _refresh_status(db: Session, invoice: Invoice) -> None:
    from sqlalchemy import func

    paid = db.scalar(
        select(func.coalesce(func.sum(InvoicePayment.amount), 0)).where(
            InvoicePayment.invoice_id == invoice.id
        )
    )
    paid = int(paid or 0)
    if paid <= 0:
        invoice.status = InvoiceStatus.ISSUED
    elif paid >= invoice.total:
        invoice.status = InvoiceStatus.PAID
    else:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    db.flush()


def issue_invoice(db: Session, company_id: int, invoice_id: int, actor_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    if invoice is None:
        raise InvoiceError("صورت‌حساب یافت نشد", code="invoice_missing", status_code=404)
    if invoice.status == InvoiceStatus.VOID:
        raise InvoiceError("صورت‌حساب باطل شده است", code="invoice_voided")
    if invoice.journal_entry_id is not None:
        raise InvoiceError("صورت‌حساب از قبل صادر شده است", code="invoice_already_issued")

    entry = create_draft_entry(
        db,
        company_id=invoice.company_id,
        actor_id=actor_id,
        entry_date=invoice.issue_date,
        memo=f"فروش: {invoice.number or f'INV-{invoice.id}'}",
        lines=[(RECEIVABLE_ACCOUNT, invoice.total, 0), (REVENUE_ACCOUNT, 0, invoice.total)],
        idempotency_key=None,
    )
    posted = post_entry(db, company_id, entry.id, actor_id)
    year, month = entry_period(invoice.issue_date)
    invoice.number = next_reference(db, invoice.company_id, year, month, "INV")
    invoice.journal_entry_id = posted.id
    invoice.status = InvoiceStatus.ISSUED
    db.flush()
    logger.info(
        "invoice issued",
        extra={"invoice_id": invoice.id, "number": invoice.number, "entry": posted.id},
    )
    return invoice


def record_payment(
    db: Session,
    *,
    company_id: int,
    invoice_id: int,
    actor_id: int,
    amount: int,
    paid_at: dt.date,
    method: str,
    reference: str | None,
) -> InvoicePayment:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    if invoice is None:
        raise InvoiceError("صورت‌حساب یافت نشد", code="invoice_missing", status_code=404)
    if invoice.status in (InvoiceStatus.DRAFT, InvoiceStatus.VOID):
        raise InvoiceError("فقط صورت‌حساب صادرشده را می‌توان پرداخت کرد", code="invoice_not_issued")
    if invoice.journal_entry_id is None:
        raise InvoiceError("صورت‌حساب هنوز صادر نشده است", code="invoice_not_issued")
    paid = sum(p.amount for p in invoice.payments)
    if paid + amount > invoice.total:
        raise InvoiceError("مبلغ پرداختی بیش از مانده است", code="invoice_overpayment")

    cash_account = "101" if method == "cash" else "102"
    entry = create_draft_entry(
        db,
        company_id=invoice.company_id,
        actor_id=actor_id,
        entry_date=paid_at,
        memo=f"دریافت وجه {invoice.number or invoice.id}",
        lines=[(cash_account, amount, 0), (RECEIVABLE_ACCOUNT, 0, amount)],
        idempotency_key=None,
    )
    posted = post_entry(db, company_id, entry.id, actor_id)
    payment = InvoicePayment(
        invoice_id=invoice.id,
        amount=amount,
        paid_at=paid_at,
        method=method,
        reference=reference,
        journal_entry_id=posted.id,
        created_by_id=actor_id,
    )
    db.add(payment)
    db.flush()
    _refresh_status(db, invoice)
    logger.info(
        "invoice payment recorded",
        extra={"invoice_id": invoice.id, "amount": amount, "entry": posted.id},
    )
    return payment


def void_invoice(db: Session, company_id: int, invoice_id: int, actor_id: int) -> Invoice:
    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    )
    if invoice is None:
        raise InvoiceError("صورت‌حساب یافت نشد", code="invoice_missing", status_code=404)
    if invoice.status == InvoiceStatus.VOID:
        raise InvoiceError("صورت‌حساب از قبل باطل شده است", code="invoice_already_voided")
    if invoice.journal_entry_id is None:
        # never issued — just mark void
        invoice.status = InvoiceStatus.VOID
        db.flush()
        return invoice
    if sum(p.amount for p in invoice.payments) > 0:
        raise InvoiceError(
            "صورت‌حسابی که پرداخت داشته را نمی‌توان باطل کرد؛ ابتدا پرداخت‌ها را بررسی کنید",
            code="invoice_has_payments",
        )
    void_entry(
        db,
        company_id,
        invoice.journal_entry_id,
        actor_id,
        memo=f"ابطال صورت‌حساب {invoice.number or invoice.id}",
    )
    invoice.status = InvoiceStatus.VOID
    db.flush()
    logger.info("invoice voided", extra={"invoice_id": invoice.id})
    return invoice


def list_invoices(db: Session, company_id: int) -> list[Invoice]:
    return list(
        db.scalars(
            select(Invoice)
            .where(Invoice.company_id == company_id)
            .order_by(Invoice.issue_date.desc(), Invoice.id.desc())
        )
    )


def get_invoice(db: Session, company_id: int, invoice_id: int) -> Invoice | None:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.company_id != company_id:
        return None
    return invoice


def invoice_metrics(invoice: Invoice, today: dt.date | None = None) -> tuple[int, int, bool]:
    """Return (paid_total, balance, is_overdue)."""
    paid = sum(p.amount for p in invoice.payments)
    balance = invoice.total - paid
    t = today or dt.date.today()
    overdue = (
        invoice.status in (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID)
        and invoice.due_date < t
    )
    return paid, balance, overdue


def get_account_checked(db: Session, company_id: int, code: str) -> object:
    """Resolve an account by code (display helper)."""
    return get_account(db, company_id, code)
