"""CRUD and stats endpoints for job applications."""

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models import Application, ApplicationStatus
from app.schemas import ApplicationCreate, ApplicationRead, ApplicationUpdate, StatsRead

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
