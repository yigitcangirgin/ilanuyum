"""CRUD and stats endpoints for job applications."""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession, Llm
from app.llm import LLMError
from app.matching import analyse_match
from app.models import Application, ApplicationStatus, MatchAnalysis
from app.schemas import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    MatchRead,
    MatchRequest,
    StatsRead,
)

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_columns(data: dict[str, Any]) -> dict[str, Any]:
    """Convert the status enum to its plain string value for storage."""
    if "status" in data:
        data["status"] = ApplicationStatus(data["status"]).value
    return data


def _get_owned(db: DbSession, user: CurrentUser, application_id: int) -> Application:
    # Başkasının kaydı için de 404 dönüyoruz ki kaydın varlığı sızmasın.
    application = db.scalars(
        select(Application).where(Application.id == application_id, Application.owner_id == user.id)
    ).first()
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    db: DbSession,
    user: CurrentUser,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[Application]:
    query = select(Application).where(Application.owner_id == user.id)
    if status_filter is not None:
        query = query.where(Application.status == status_filter.value)
    query = (
        query.order_by(Application.applied_at.desc(), Application.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(query).all())


# /stats, /{application_id} yolundan ÖNCE tanımlanmalı, yoksa "stats" id sanılır.
@router.get("/stats", response_model=StatsRead)
def application_stats(db: DbSession, user: CurrentUser) -> StatsRead:
    rows = db.execute(
        select(Application.status, func.count())
        .where(Application.owner_id == user.id)
        .group_by(Application.status)
    ).all()
    by_status = {item.value: 0 for item in ApplicationStatus}
    for status_value, count in rows:
        by_status[status_value] = count
    return StatsRead(total=sum(by_status.values()), by_status=by_status)


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: DbSession, user: CurrentUser) -> Application:
    application = Application(owner_id=user.id, **_to_columns(payload.model_dump()))
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(application_id: int, db: DbSession, user: CurrentUser) -> Application:
    return _get_owned(db, user, application_id)


@router.put("/{application_id}", response_model=ApplicationRead)
def replace_application(
    application_id: int, payload: ApplicationCreate, db: DbSession, user: CurrentUser
) -> Application:
    application = _get_owned(db, user, application_id)
    for field, value in _to_columns(payload.model_dump()).items():
        setattr(application, field, value)
    db.commit()
    db.refresh(application)
    return application


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: int, payload: ApplicationUpdate, db: DbSession, user: CurrentUser
) -> Application:
    application = _get_owned(db, user, application_id)
    for field, value in _to_columns(payload.model_dump(exclude_unset=True)).items():
        setattr(application, field, value)
    db.commit()
    db.refresh(application)
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: int, db: DbSession, user: CurrentUser) -> Response:
    application = _get_owned(db, user, application_id)
    db.delete(application)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{application_id}/match",
    response_model=MatchRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "No job description on the application or in the request"},
        502: {"description": "The LLM provider failed or returned an invalid analysis"},
        503: {"description": "No LLM API key configured"},
    },
)
def create_match_analysis(
    application_id: int, payload: MatchRequest, db: DbSession, user: CurrentUser, llm: Llm
) -> MatchAnalysis:
    """Compare a CV with the application's job posting using an LLM and store the result.

    The CV text is used only for this request and is not stored.
    """
    application = _get_owned(db, user, application_id)
    if payload.job_description is not None:
        application.job_description = payload.job_description
    job_description = (application.job_description or "").strip()
    if not job_description:
        raise HTTPException(
            status_code=422,
            detail="Add a job_description to the application or send one in the request",
        )

    try:
        result = analyse_match(
            llm, payload.cv_text, job_description, application.position, application.company
        )
    except LLMError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    analysis = MatchAnalysis(application_id=application.id, model=llm.model, **result.model_dump())
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{application_id}/matches", response_model=list[MatchRead])
def list_match_analyses(
    application_id: int, db: DbSession, user: CurrentUser
) -> list[MatchAnalysis]:
    """Previous analyses for one application, newest first."""
    application = _get_owned(db, user, application_id)
    query = (
        select(MatchAnalysis)
        .where(MatchAnalysis.application_id == application.id)
        .order_by(MatchAnalysis.created_at.desc(), MatchAnalysis.id.desc())
    )
    return list(db.scalars(query).all())
