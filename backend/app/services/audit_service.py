from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogPage, AuditLogQuery, AuditLogRead, AuditLogStatsResponse

logger = logging.getLogger(__name__)


class AuditAction:
    AUTH_LOGIN = "auth.login"
    AUTH_REGISTER = "auth.register"
    AUTH_LOGOUT = "auth.logout"
    ANNOTATION_SUBMITTED = "annotation.submitted"
    ANNOTATION_UPDATED = "annotation.updated"
    REVIEW_ASSIGNED = "review.assigned"
    REVIEW_SUBMITTED = "review.submitted"
    REVIEW_APPROVED = "review.approved"
    REVIEW_REJECTED = "review.rejected"
    TASK_PACK_CREATED = "task_pack.created"
    TASK_PACK_UPDATED = "task_pack.updated"
    TASK_PACK_DELETED = "task_pack.deleted"
    DATASET_CREATED = "dataset.created"
    DATASET_EXPORTED = "dataset.exported"
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    MEMBER_INVITED = "member.invited"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    WEBHOOK_CREATED = "webhook.created"
    WEBHOOK_DELETED = "webhook.deleted"
    ORG_SETTINGS_UPDATED = "org.settings_updated"


async def log(
    db: AsyncSession,
    actor_id: uuid.UUID | None,
    org_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    details: dict[str, Any] | None,
    ip_address: str | None,
) -> None:
    """Persist an audit row in its own session/commit so callers need not commit.

    The request ``db`` is accepted for API symmetry with other services; logging uses a
    dedicated session so ``asyncio.create_task(audit_service.log(db, ...))`` does not
    race with the request session lifecycle.
    """
    _ = db
    row = AuditLog(
        actor_id=actor_id,
        org_id=org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details_json=details,
        ip_address=ip_address,
    )
    try:
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception:
        logger.exception("audit log write failed action=%s resource_type=%s", action, resource_type)


def _apply_filters(q: Any, filters: AuditLogQuery) -> Any:
    conditions: list[Any] = []
    if filters.actor_id is not None:
        conditions.append(AuditLog.actor_id == filters.actor_id)
    if filters.action is not None and filters.action.strip():
        conditions.append(AuditLog.action.like(filters.action.strip() + "%"))
    if filters.resource_type is not None and filters.resource_type.strip():
        conditions.append(AuditLog.resource_type == filters.resource_type.strip())
    if filters.resource_id is not None and filters.resource_id.strip():
        conditions.append(AuditLog.resource_id == filters.resource_id.strip())
    if filters.start_date is not None:
        conditions.append(AuditLog.created_at >= filters.start_date)
    if filters.end_date is not None:
        conditions.append(AuditLog.created_at <= filters.end_date)
    if conditions:
        return q.where(and_(*conditions))
    return q


async def query(db: AsyncSession, filters: AuditLogQuery) -> AuditLogPage:
    base = select(AuditLog)
    base = _apply_filters(base, filters)
    count_stmt = select(func.count()).select_from(AuditLog)
    count_stmt = _apply_filters(count_stmt, filters)
    total = (await db.execute(count_stmt)).scalar_one()
    limit = max(1, min(filters.limit, 500))
    skip = max(0, filters.skip)
    page_stmt = (
        base.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    )
    result = await db.execute(page_stmt)
    rows = result.scalars().all()
    return AuditLogPage(
        items=[AuditLogRead.model_validate(r) for r in rows],
        total=int(total),
        skip=skip,
        limit=limit,
    )


async def get_actor_activity(
    db: AsyncSession,
    actor_id: uuid.UUID,
    limit: int,
) -> list[AuditLogRead]:
    lim = max(1, min(limit, 500))
    stmt = (
        select(AuditLog)
        .where(AuditLog.actor_id == actor_id)
        .order_by(AuditLog.created_at.desc())
        .limit(lim)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [AuditLogRead.model_validate(r) for r in rows]


async def get_resource_history(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
) -> list[AuditLogRead]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.resource_type == resource_type)
        .where(AuditLog.resource_id == resource_id)
        .order_by(AuditLog.created_at.asc())
        .limit(10_000)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [AuditLogRead.model_validate(r) for r in rows]


async def get_stats(db: AsyncSession) -> AuditLogStatsResponse:
    now = datetime.now(UTC)

    async def _window_counts(since: datetime) -> dict[str, int]:
        stmt = (
            select(AuditLog.action, func.count())
            .where(AuditLog.created_at >= since)
            .group_by(AuditLog.action)
        )
        result = await db.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    return AuditLogStatsResponse(
        last_24h=await _window_counts(now - timedelta(hours=24)),
        last_7d=await _window_counts(now - timedelta(days=7)),
        last_30d=await _window_counts(now - timedelta(days=30)),
    )
