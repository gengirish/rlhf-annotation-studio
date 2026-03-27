from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator
from app.schemas.metrics import SessionMetricsSummary, SessionTimeline
from app.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/session/{session_id}/summary", response_model=SessionMetricsSummary)
async def get_session_metrics_summary(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> SessionMetricsSummary:
    return await MetricsService(db).get_session_summary(session_id=session_id, user_id=current_user.id)


@router.get("/session/{session_id}/timeline", response_model=SessionTimeline)
async def get_session_metrics_timeline(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> SessionTimeline:
    return await MetricsService(db).get_session_timeline(session_id=session_id, user_id=current_user.id)
