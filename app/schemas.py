"""Pydantic schemas (request and response bodies)."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.models import ApplicationStatus

JOB_DESCRIPTION_MAX = 20_000
CV_TEXT_MAX = 20_000

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def _clean_job_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise ValueError("job_url must start with http:// or https://")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApplicationBase(BaseModel):
    company: Name
    position: Name
    job_url: str | None = Field(default=None, max_length=500)
    status: ApplicationStatus = ApplicationStatus.APPLIED
    applied_at: date = Field(default_factory=date.today)
    notes: str | None = Field(default=None, max_length=5000)
    job_description: str | None = Field(default=None, max_length=JOB_DESCRIPTION_MAX)

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str | None) -> str | None:
        return _clean_job_url(value)


class ApplicationCreate(ApplicationBase):
    """Body for POST and PUT (full replace)."""


class ApplicationUpdate(BaseModel):
    """Body for PATCH: every field optional."""

    company: Name | None = None
    position: Name | None = None
    job_url: str | None = Field(default=None, max_length=500)
    status: ApplicationStatus | None = None
    applied_at: date | None = None
    notes: str | None = Field(default=None, max_length=5000)
    job_description: str | None = Field(default=None, max_length=JOB_DESCRIPTION_MAX)

    @field_validator("job_url")
    @classmethod
    def validate_job_url(cls, value: str | None) -> str | None:
        return _clean_job_url(value)

    @field_validator("company", "position", "status", "applied_at")
    @classmethod
    def reject_null(cls, value: object) -> object:
        # Bu kolonlar NOT NULL; PATCH ile açıkça null gönderilmesini engelle.
        if value is None:
            raise ValueError("this field cannot be null")
        return value


class ApplicationRead(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StatsRead(BaseModel):
    total: int
    by_status: dict[str, int]


SkillList = Annotated[list[Annotated[str, StringConstraints(max_length=100)]], Field(max_length=20)]


class MatchRequest(BaseModel):
    """Body for POST /applications/{id}/match."""

    cv_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=50, max_length=CV_TEXT_MAX)
    ]
    # Optional: overrides (and is saved as) the application's job description.
    job_description: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=50, max_length=JOB_DESCRIPTION_MAX),
        ]
        | None
    ) = None


class MatchResult(BaseModel):
    """What the LLM must return. Validated strictly before anything is stored."""

    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=1000)
    matched_skills: SkillList = Field(default_factory=list)
    missing_skills: SkillList = Field(default_factory=list)
    suggestions: Annotated[
        list[Annotated[str, StringConstraints(max_length=300)]], Field(max_length=10)
    ] = Field(default_factory=list)


class MatchRead(MatchResult):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    model: str
    created_at: datetime
