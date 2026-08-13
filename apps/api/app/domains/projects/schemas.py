"""Projects Pydantic schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.projects.models import ProjectStatus


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    status: ProjectStatus = ProjectStatus.ACTIVE
    description: str | None = Field(default=None, max_length=600)
    responsible_person: str | None = Field(default=None, max_length=200)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _dates_consistent(self) -> ProjectCreate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("تاریخ پایان نمیتواند قبل از تاریخ شروع باشد")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: ProjectStatus | None = None
    description: str | None = Field(default=None, max_length=600)
    responsible_person: str | None = Field(default=None, max_length=200)
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget: int | None = Field(default=None, ge=0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: ProjectStatus
    description: str | None = None
    responsible_person: str | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    budget: int
    created_at: dt.datetime
