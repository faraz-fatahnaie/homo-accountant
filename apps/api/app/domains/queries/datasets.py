# mypy: disable-error-code="type-arg,arg-type,index,no-any-return,operator,union-attr,attr-defined"
"""Query-builder datasets: the ALLOWLIST.

Every dataset declares its columns (field → label → type) and the SQLAlchemy
expression used to read each field. The compiler ONLY resolves field names
against this map — anything else is rejected, so arbitrary SQL can never
reach the database. All queries are scoped to the caller's company and run
with a statement timeout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.domains.bills.models import Bill
from app.domains.contacts.models import Contact
from app.domains.expenses.models import Expense
from app.domains.funding.models import FundingEvent
from app.domains.invoices.models import Invoice
from app.domains.ledger.models import Account, JournalEntry, JournalLine
from app.domains.projects.models import Project

# correlated total for a journal entry (sum of line debits)
_ENTRY_TOTAL = (
    select(func.coalesce(func.sum(JournalLine.debit), 0))
    .where(JournalLine.entry_id == JournalEntry.id)
    .correlate(JournalEntry)
    .scalar_subquery()
)

# reusable aliases for joined name columns
_Contact = aliased(Contact)
_Project = aliased(Project)
_Account = aliased(Account)


@dataclass(frozen=True)
class ColumnDef:
    label: str
    type: str  # string | date | amount | enum | bool
    expr: object
    enum_options: list[str] = field(default_factory=list)
    amount: bool = False


@dataclass(frozen=True)
class DatasetDef:
    label: str
    columns: dict[str, ColumnDef]
    base: object  # SQLAlchemy model
    joins: tuple = ()  # (selectable, onclause, is_outer) applied by compiler


DATASETS: dict[str, DatasetDef] = {
    "journal_entries": DatasetDef(
        label="سندهای حسابداری",
        base=JournalEntry,
        columns={
            "entry_date": ColumnDef("تاریخ", "date", JournalEntry.entry_date),
            "reference": ColumnDef("شماره", "string", JournalEntry.reference),
            "memo": ColumnDef("شرح", "string", JournalEntry.memo),
            "status": ColumnDef("وضعیت", "enum", JournalEntry.status, ["draft", "posted"]),
            "total": ColumnDef("مبلغ", "amount", _ENTRY_TOTAL, amount=True),
        },
    ),
    "expenses": DatasetDef(
        label="هزینه‌ها",
        base=Expense,
        joins=(
            (_Contact, Expense.contact_id == _Contact.id, True),
            (_Project, Expense.project_id == _Project.id, True),
            (_Account, Expense.account_id == _Account.id, True),
        ),
        columns={
            "number": ColumnDef("شماره", "string", Expense.number),
            "entry_date": ColumnDef("تاریخ", "date", Expense.entry_date),
            "description": ColumnDef("شرح", "string", Expense.description),
            "contact_name": ColumnDef("طرف‌حساب", "string", _Contact.name),
            "project_name": ColumnDef("پروژه", "string", _Project.name),
            "account_code": ColumnDef("کد حساب", "string", _Account.code),
            "account_name": ColumnDef("حساب", "string", _Account.name),
            "amount": ColumnDef("مبلغ", "amount", Expense.amount, amount=True),
            "payment_method": ColumnDef(
                "روش پرداخت", "enum", Expense.payment_method, ["cash", "bank", "online"]
            ),
            "status": ColumnDef("وضعیت", "enum", Expense.status, ["draft", "posted", "voided"]),
        },
    ),
    "invoices": DatasetDef(
        label="صورت‌حساب‌های فروش",
        base=Invoice,
        joins=(
            (_Contact, Invoice.customer_id == _Contact.id, True),
            (_Project, Invoice.project_id == _Project.id, True),
        ),
        columns={
            "number": ColumnDef("شماره", "string", Invoice.number),
            "customer_name": ColumnDef("مشتری", "string", _Contact.name),
            "project_name": ColumnDef("پروژه", "string", _Project.name),
            "issue_date": ColumnDef("تاریخ صدور", "date", Invoice.issue_date),
            "due_date": ColumnDef("سررسید", "date", Invoice.due_date),
            "total": ColumnDef("مبلغ کل", "amount", Invoice.total, amount=True),
            "status": ColumnDef(
                "وضعیت",
                "enum",
                Invoice.status,
                ["draft", "issued", "partially_paid", "paid", "void"],
            ),
        },
    ),
    "bills": DatasetDef(
        label="فاکتورهای خرید",
        base=Bill,
        joins=(
            (_Contact, Bill.vendor_id == _Contact.id, True),
            (_Project, Bill.project_id == _Project.id, True),
            (_Account, Bill.account_id == _Account.id, True),
        ),
        columns={
            "number": ColumnDef("شماره", "string", Bill.number),
            "vendor_name": ColumnDef("تأمین‌کننده", "string", _Contact.name),
            "project_name": ColumnDef("پروژه", "string", _Project.name),
            "account_code": ColumnDef("کد حساب", "string", _Account.code),
            "account_name": ColumnDef("حساب", "string", _Account.name),
            "issue_date": ColumnDef("تاریخ فاکتور", "date", Bill.issue_date),
            "due_date": ColumnDef("سررسید", "date", Bill.due_date),
            "memo": ColumnDef("شرح", "string", Bill.memo),
            "total": ColumnDef("مبلغ", "amount", Bill.total, amount=True),
            "status": ColumnDef(
                "وضعیت", "enum", Bill.status, ["draft", "open", "partially_paid", "paid", "void"]
            ),
        },
    ),
    "funding": DatasetDef(
        label="تأمین مالی",
        base=FundingEvent,
        joins=(
            (_Contact, FundingEvent.contact_id == _Contact.id, True),
            (_Project, FundingEvent.project_id == _Project.id, True),
        ),
        columns={
            "number": ColumnDef("شماره", "string", FundingEvent.number),
            "funding_type": ColumnDef(
                "نوع", "enum", FundingEvent.funding_type, ["investment", "loan", "grant", "revenue"]
            ),
            "contact_name": ColumnDef("طرف‌حساب", "string", _Contact.name),
            "event_date": ColumnDef("تاریخ", "date", FundingEvent.event_date),
            "amount": ColumnDef("مبلغ", "amount", FundingEvent.amount, amount=True),
            "method": ColumnDef("روش", "enum", FundingEvent.method, ["cash", "bank", "online"]),
            "agreement_ref": ColumnDef("مرجع", "string", FundingEvent.agreement_ref),
            "maturity_date": ColumnDef("سررسید", "date", FundingEvent.maturity_date),
        },
    ),
    "contacts": DatasetDef(
        label="طرف‌حساب‌ها",
        base=Contact,
        columns={
            "name": ColumnDef("نام", "string", Contact.name),
            "phone": ColumnDef("تلفن", "string", Contact.phone),
            "email": ColumnDef("ایمیل", "string", Contact.email),
            "payment_terms_days": ColumnDef("شرایط پرداخت", "amount", Contact.payment_terms_days),
            "is_active": ColumnDef("فعال", "bool", Contact.is_active),
        },
    ),
    "projects": DatasetDef(
        label="پروژه‌ها",
        base=Project,
        columns={
            "name": ColumnDef("نام", "string", Project.name),
            "status": ColumnDef(
                "وضعیت", "enum", Project.status, ["active", "completed", "on_hold"]
            ),
            "responsible_person": ColumnDef("مسئول", "string", Project.responsible_person),
            "budget": ColumnDef("بودجه", "amount", Project.budget, amount=True),
        },
    ),
}


def column_for(dataset: str, field: str) -> ColumnDef | None:
    d = DATASETS.get(dataset)
    if d is None:
        return None
    return d.columns.get(field)
