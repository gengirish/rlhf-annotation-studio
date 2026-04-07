from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogQuery
from app.services.audit_service import AuditAction, get_actor_activity, log, query


async def _audit_table_ready() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(AuditLog).limit(1))
        return True
    except (ProgrammingError, DBAPIError, OSError):
        return False


@pytest.fixture
async def db_session() -> AsyncSession:
    if not await _audit_table_ready():
        pytest.skip(
            "audit_logs table missing or DB unreachable; apply migrations (alembic upgrade head)"
        )
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AuditLog))
        await session.commit()
        yield session
        await session.rollback()


@pytest.mark.asyncio
async def test_log_creates_with_all_fields(db_session: AsyncSession) -> None:
    oid = uuid.uuid4()
    rid = str(uuid.uuid4())
    details = {"old_value": "a", "new_value": "b", "user_agent": "pytest"}
    await log(
        db_session,
        actor_id=None,
        org_id=oid,
        action=AuditAction.AUTH_LOGIN,
        resource_type="annotator",
        resource_id=rid,
        details=details,
        ip_address="2001:db8::1",
    )
    async with AsyncSessionLocal() as read_session:
        result = await read_session.execute(select(AuditLog).where(AuditLog.resource_id == rid))
        row = result.scalar_one()
        assert row.actor_id is None
        assert row.org_id == oid
        assert row.action == AuditAction.AUTH_LOGIN
        assert row.resource_type == "annotator"
        assert row.resource_id == rid
        assert row.details_json == details
        assert row.ip_address == "2001:db8::1"
        assert row.created_at is not None


@pytest.mark.asyncio
async def test_query_filters_by_action_prefix(db_session: AsyncSession) -> None:
    await log(
        db_session,
        None,
        None,
        AuditAction.AUTH_LOGIN,
        "annotator",
        None,
        None,
        None,
    )
    await log(
        db_session,
        None,
        None,
        AuditAction.AUTH_REGISTER,
        "annotator",
        None,
        None,
        None,
    )
    await log(
        db_session,
        None,
        None,
        AuditAction.ANNOTATION_SUBMITTED,
        "task_pack",
        "tp-1",
        None,
        None,
    )
    page = await query(db_session, AuditLogQuery(action="auth.", limit=50))
    assert page.total == 2
    actions = {item.action for item in page.items}
    assert actions == {AuditAction.AUTH_LOGIN, AuditAction.AUTH_REGISTER}


@pytest.mark.asyncio
async def test_query_date_range(db_session: AsyncSession) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    mid = now - timedelta(days=5)

    async def _add_at(created_at: datetime, suffix: str) -> None:
        async with AsyncSessionLocal() as s:
            s.add(
                AuditLog(
                    action=f"test.action.{suffix}",
                    resource_type="dataset",
                    resource_id=suffix,
                    created_at=created_at,
                )
            )
            await s.commit()

    await _add_at(old, "old")
    await _add_at(mid, "mid")
    await _add_at(now, "new")

    start = now - timedelta(days=7)
    end = now - timedelta(days=1)
    page = await query(
        db_session,
        AuditLogQuery(start_date=start, end_date=end, limit=50),
    )
    assert page.total == 1
    assert page.items[0].resource_id == "mid"


@pytest.mark.asyncio
async def test_query_pagination(db_session: AsyncSession) -> None:
    for i in range(5):
        await log(
            db_session,
            None,
            None,
            f"pagination.test.{i}",
            "review",
            str(i),
            None,
            None,
        )
    page0 = await query(db_session, AuditLogQuery(action="pagination.test.", skip=0, limit=2))
    page1 = await query(db_session, AuditLogQuery(action="pagination.test.", skip=2, limit=2))
    assert page0.total == 5
    assert page1.total == 5
    assert len(page0.items) == 2
    assert len(page1.items) == 2
    ids0 = {x.resource_id for x in page0.items}
    ids1 = {x.resource_id for x in page1.items}
    assert ids0.isdisjoint(ids1)


@pytest.mark.asyncio
async def test_get_actor_activity(db_session: AsyncSession) -> None:
    aid = uuid.uuid4()
    for i in range(3):
        async with AsyncSessionLocal() as s:
            s.add(
                AuditLog(
                    actor_id=aid,
                    action=f"activity.{i}",
                    resource_type="annotator",
                    resource_id=str(i),
                )
            )
            await s.commit()
    rows = await get_actor_activity(db_session, aid, limit=2)
    assert len(rows) == 2
    assert all(r.actor_id == aid for r in rows)
