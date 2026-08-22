"""Invoices API routes (incl. PDF download)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.core.http import attachment_disposition
from app.core.jalali import format_jalali, gregorian_to_jalali
from app.domains.contacts.service import get_contact
from app.domains.identity.models import Role, User
from app.domains.invoices.models import Invoice
from app.domains.invoices.pdf import render_invoice_pdf
from app.domains.invoices.schemas import (
    InvoiceCreate,
    InvoiceOut,
    InvoicePaymentOut,
    PaymentIn,
)
from app.domains.invoices.service import (
    InvoiceError,
    create_invoice,
    get_invoice,
    invoice_metrics,
    issue_invoice,
    list_invoices,
    record_payment,
    void_invoice,
)

router = APIRouter(tags=["invoices"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)


def _to_out(db: Session, invoice: Invoice) -> InvoiceOut:
    paid, balance, overdue = invoice_metrics(invoice)
    customer = get_contact(db, invoice.company_id, invoice.customer_id)
    return InvoiceOut(
        id=invoice.id,
        number=invoice.number,
        customer_id=invoice.customer_id,
        customer_name=customer.name if customer else "—",
        project_id=invoice.project_id,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        status=invoice.status,
        notes=invoice.notes,
        payment_instructions=invoice.payment_instructions,
        total=invoice.total,
        paid_total=paid,
        balance=balance,
        is_overdue=overdue,
        journal_entry_id=invoice.journal_entry_id,
        created_at=invoice.created_at,
        items=list(invoice.items),
        payments=list(invoice.payments),
    )


def _handle(exc: InvoiceError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


@router.get("/invoices", response_model=list[InvoiceOut])
def invoices_list(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[InvoiceOut]:
    return [_to_out(db, inv) for inv in list_invoices(db, user.company_id)]


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def invoices_create(
    payload: InvoiceCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> InvoiceOut | JSONResponse:
    customer = get_contact(db, actor.company_id, payload.customer_id)
    if customer is None:
        return error_response(404, "not_found", "مشتری یافت نشد")
    try:
        invoice = create_invoice(
            db,
            company_id=actor.company_id,
            actor_id=actor.id,
            customer_id=payload.customer_id,
            project_id=payload.project_id,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            items=[it.model_dump() for it in payload.items],
            notes=payload.notes,
            payment_instructions=payload.payment_instructions,
        )
    except InvoiceError as exc:
        return _handle(exc)
    db.commit()
    return _to_out(db, invoice)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def invoices_detail(
    invoice_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> InvoiceOut | JSONResponse:
    invoice = get_invoice(db, user.company_id, invoice_id)
    if invoice is None:
        return error_response(404, "not_found", "صورت‌حساب یافت نشد")
    return _to_out(db, invoice)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceOut)
def invoices_issue(
    invoice_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> InvoiceOut | JSONResponse:
    try:
        invoice = issue_invoice(db, actor.company_id, invoice_id, actor.id)
    except InvoiceError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, invoice)


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoicePaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def invoices_pay(
    invoice_id: int,
    payload: PaymentIn,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> InvoicePaymentOut | JSONResponse:
    try:
        payment = record_payment(
            db,
            company_id=actor.company_id,
            invoice_id=invoice_id,
            actor_id=actor.id,
            amount=payload.amount,
            paid_at=payload.paid_at,
            method=payload.method,
            reference=payload.reference,
        )
    except InvoiceError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return InvoicePaymentOut.model_validate(payment)


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceOut)
def invoices_void(
    invoice_id: int,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> InvoiceOut | JSONResponse:
    try:
        invoice = void_invoice(db, actor.company_id, invoice_id, actor.id)
    except InvoiceError as exc:
        db.rollback()
        return _handle(exc)
    db.commit()
    return _to_out(db, invoice)


@router.get("/invoices/{invoice_id}/pdf", response_model=None)
def invoices_pdf(
    invoice_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response | JSONResponse:
    invoice = get_invoice(db, user.company_id, invoice_id)
    if invoice is None:
        return error_response(404, "not_found", "صورت‌حساب یافت نشد")
    customer = get_contact(db, user.company_id, invoice.customer_id)
    paid, balance, _ = invoice_metrics(invoice)
    items = [
        {
            "description": it.description,
            "quantity": it.quantity,
            "unit_price": it.unit_price,
            "line_total": it.line_total,
        }
        for it in invoice.items
    ]
    pdf = render_invoice_pdf(
        company_name="شرکت آریا تجارت",
        invoice_number=invoice.number or f"INV-{invoice.id}",
        customer_name=customer.name if customer else "—",
        issue_date=format_jalali(gregorian_to_jalali(invoice.issue_date), with_month_name=True),
        due_date=format_jalali(gregorian_to_jalali(invoice.due_date), with_month_name=True),
        items=items,
        total=invoice.total,
        paid=paid,
        balance=balance,
        notes=invoice.notes,
        payment_instructions=invoice.payment_instructions,
    )
    filename = f"invoice-{invoice.number or invoice.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_disposition(filename)},
    )
