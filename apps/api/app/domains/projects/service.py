"""Projects service."""

from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.projects.models import Project

logger = logging.getLogger(__name__)


class ProjectError(Exception):
    def __init__(self, message: str, code: str = "project_error", status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def list_projects(db: Session, company_id: int, *, active_only: bool = False) -> list[Project]:
    stmt = select(Project).where(Project.company_id == company_id)
    if active_only:
        stmt = stmt.where(Project.status == "active")
    return list(db.scalars(stmt.order_by(Project.name)))


def get_project(db: Session, company_id: int, project_id: int) -> Project | None:
    project = db.get(Project, project_id)
    if project is None or project.company_id != company_id:
        return None
    return project


def create_project(
    db: Session,
    *,
    company_id: int,
    name: str,
    status: str,
    description: str | None,
    responsible_person: str | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    budget: int,
) -> Project:
    if start_date and end_date and end_date < start_date:
        raise ProjectError(
            "تاریخ پایان نمیتواند قبل از تاریخ شروع باشد", code="project_dates_invalid"
        )
    project = Project(
        company_id=company_id,
        name=name.strip(),
        status=status,
        description=description,
        responsible_person=responsible_person,
        start_date=start_date,
        end_date=end_date,
        budget=budget,
    )
    db.add(project)
    db.flush()
    logger.info("project created", extra={"project_id": project.id, "project_name": project.name})
    return project


def update_project(db: Session, project: Project, **changes: object) -> Project:
    for key, value in changes.items():
        if value is not None:
            setattr(project, key, value)
    db.flush()
    return project
