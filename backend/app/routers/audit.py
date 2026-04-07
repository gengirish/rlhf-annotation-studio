from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.db import get_db
from app.models.annotator import Annotator
from app.schemas.audit_log import AuditLogPage, AuditLogQuery, AuditLogRead, AuditLogStatsResponse
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogPage)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Annotator, Depends(require_admin)],
    actor_id: UUID | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> AuditLogPage:
    filters = AuditLogQuery(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
    return await audit_service.query(db, filters)


@router.get("/logs/me", response_model=list[AuditLogRead])
async def list_my_audit_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Annotator, Depends(get_current_user)],
    limit: int = Query(50, ge=1, le=500),
) -> list[AuditLogRead]:
    return await audit_service.get_actor_activity(db, current_user.id, limit)


@router.get("/logs/resource/{resource_type}/{resource_id}", response_model=list[AuditLogRead])
async def list_resource_audit_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Annotator, Depends(require_admin)],
    resource_type: str,
    resource_id: str,
) -> list[AuditLogRead]:
    return await audit_service.get_resource_history(db, resource_type, resource_id)


@router.get("/stats", response_model=AuditLogStatsResponse)
async def audit_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Annotator, Depends(require_admin)],
) -> AuditLogStatsResponse:
    return await audit_service.get_stats(db)
