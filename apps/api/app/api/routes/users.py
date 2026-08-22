"""User management (OWNER only) + current user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.core.db import get_db
from app.domains.identity.models import Role, User
from app.domains.identity.schemas import UserCreate, UserOut
from app.domains.identity.service import AuthError, create_user, list_users

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user


@router.get("/users", response_model=list[UserOut])
def users_list(
    actor: User = Depends(require_roles(Role.OWNER)), db: Session = Depends(get_db)
) -> list[User]:
    return list_users(db, actor.company_id)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def users_create(
    payload: UserCreate,
    actor: User = Depends(require_roles(Role.OWNER)),
    db: Session = Depends(get_db),
) -> User:
    try:
        user = create_user(
            db,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            role=payload.role,
            company=actor.company,
        )
    except AuthError as exc:
        raise HTTPException(exc.status_code, detail=exc.message) from exc
    db.commit()
    return user
