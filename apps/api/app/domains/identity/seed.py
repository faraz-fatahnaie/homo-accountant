"""Development seeding: one company, demo users, chart of accounts, periods.

Never run with production credentials; guarded by HOMO_SEED_DEMO_USERS=true and
refused in production environments. `seed_dev_data` is called on API startup in
dev so `docker compose up` works out of the box.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domains.identity.models import Role
from app.domains.identity.service import create_user, ensure_default_company

logger = logging.getLogger(__name__)

DEMO_USERS: list[tuple[str, str, str, Role]] = [
    ("owner@example.com", "مدیر سامانه", "owner-homo-1405", Role.OWNER),
    ("accountant@example.com", "نگار رضایی", "acct-homo-1405", Role.ACCOUNTANT),
    ("staff@example.com", "سامان کریمی", "staff-homo-1405", Role.STAFF),
    ("viewer@example.com", "مهمان بیننده", "viewer-homo-1405", Role.VIEWER),
]

_FISCAL_YEAR = 1405


def seed_demo_users(db: Session) -> int:
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("refusing to seed demo users in production")
    ensure_default_company(db)
    created = 0
    for email, name, password, role in DEMO_USERS:
        try:
            create_user(db, email=email, full_name=name, password=password, role=role)
            created += 1
        except Exception:  # already exists
            db.rollback()
    db.commit()
    return created


DEMO_CONTACTS: list[tuple[str, list[str], str | None, int]] = [
    ("بازرگانی خلیجفارس", ["customer"], "۰۲۱-۸۸۷۶۵۴۳۲", 30),
    ("فولاد البرز", ["vendor"], "۰۲۱-۶۶۵۵۴۳۲۱", 30),
    ("شرکت سرمایهگذاری امید", ["investor"], "۰۲۱-۲۲۳۳۴۴۵۵", 0),
    ("بانک ملت", ["lender"], "۰۲۱-۸۸۹۹۰۰۱۱", 0),
]

DEMO_PROJECTS: list[tuple[str, str, int]] = [
    ("بازسازی انبار مرکزی", "active", 500_000_000),
    ("طراحی وبسایت فروشگاهی", "active", 200_000_000),
    ("توسعه صادرات", "active", 300_000_000),
]


def _seed_demo_crm(db: Session, company_id: int) -> tuple[int, int]:
    from sqlalchemy import select

    from app.domains.contacts.models import Contact
    from app.domains.projects.models import Project

    existing_contacts = len(
        list(db.scalars(select(Contact).where(Contact.company_id == company_id)))
    )
    created_contacts = 0
    if existing_contacts == 0:
        for name, roles, phone, terms in DEMO_CONTACTS:
            db.add(
                Contact(
                    company_id=company_id,
                    name=name,
                    roles=roles,
                    phone=phone,
                    payment_terms_days=terms,
                )
            )
            created_contacts += 1
    existing_projects = len(
        list(db.scalars(select(Project).where(Project.company_id == company_id)))
    )
    created_projects = 0
    if existing_projects == 0:
        for name, status, budget in DEMO_PROJECTS:
            db.add(Project(company_id=company_id, name=name, status=status, budget=budget))
            created_projects += 1
    db.flush()
    return created_contacts, created_projects


def seed_dev_data(db: Session) -> dict[str, int]:
    """Idempotent full dev bootstrap: company + demo users + chart + periods + CRM."""
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError("refusing to seed dev data in production")

    from app.domains.funding.service import ensure_default_mappings
    from app.domains.ledger.service import get_period, seed_chart_of_accounts

    company = ensure_default_company(db)
    users = seed_demo_users(db)
    chart = seed_chart_of_accounts(db, company.id)
    funding = ensure_default_mappings(db, company.id)
    periods = 0
    for month in range(1, 13):
        get_period(db, company.id, _FISCAL_YEAR, month)
        periods += 1
    contacts, projects = _seed_demo_crm(db, company.id)
    db.commit()
    return {
        "users": users,
        "chart_accounts": chart,
        "periods": periods,
        "funding_mappings": funding,
        "contacts": contacts,
        "projects": projects,
    }
