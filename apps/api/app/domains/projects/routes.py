"""Projects API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.errors import error_response
from app.core.db import get_db
from app.domains.identity.models import Role, User
from app.domains.projects.models import Project
from app.domains.projects.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.domains.projects.service import (
    ProjectError,
    create_project,
    get_project,
    list_projects,
    update_project,
)

router = APIRouter(tags=["projects"])
WRITERS = (Role.OWNER, Role.ACCOUNTANT)


@router.get("/projects", response_model=list[ProjectOut])
def projects_list(
    user: User = Depends(current_user),
    active_only: bool = False,
    db: Session = Depends(get_db),
) -> list[Project]:
    return list_projects(db, user.company_id, active_only=active_only)


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def projects_create(
    payload: ProjectCreate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Project | JSONResponse:
    try:
        project = create_project(
            db,
            company_id=actor.company_id,
            name=payload.name,
            status=payload.status.value,
            description=payload.description,
            responsible_person=payload.responsible_person,
            start_date=payload.start_date,
            end_date=payload.end_date,
            budget=payload.budget,
        )
    except ProjectError as exc:
        return error_response(exc.status_code, exc.code, exc.message)
    db.commit()
    return project


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def projects_update(
    project_id: int,
    payload: ProjectUpdate,
    actor: User = Depends(require_roles(*WRITERS)),
    db: Session = Depends(get_db),
) -> Project | JSONResponse:
    project = get_project(db, actor.company_id, project_id)
    if project is None:
        return error_response(404, "not_found", "پروژه یافت نشد")
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    update_project(db, project, **changes)
    db.commit()
    return project
