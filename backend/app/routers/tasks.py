from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, TaskPack, WorkSession
from app.schemas.gold_scoring import GoldScoreRequest, GoldScoreResponse
from app.schemas.task_pack import TaskPackDetail, TaskPackListResponse, TaskPackSummary
from app.schemas.task_validation import TaskValidationRequest, TaskValidationResponse
from app.services.gold_scoring_service import GoldScoringService
from app.services.task_validation_service import TaskValidationService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/validate", response_model=TaskValidationResponse)
async def validate_tasks(body: TaskValidationRequest) -> TaskValidationResponse:
    issues, invalid_rows = TaskValidationService().validate_tasks(body.tasks)
    valid_tasks = len(body.tasks) - len(invalid_rows)
    ok = not issues if body.strict_mode else valid_tasks > 0
    return TaskValidationResponse(
        ok=ok,
        strict_mode=body.strict_mode,
        total_tasks=len(body.tasks),
        valid_tasks=max(valid_tasks, 0),
        issues=issues,
    )


@router.get("/packs", response_model=TaskPackListResponse)
async def list_task_packs(db: AsyncSession = Depends(get_db)) -> TaskPackListResponse:
    result = await db.execute(select(TaskPack).order_by(TaskPack.name))
    packs = result.scalars().all()
    return TaskPackListResponse(packs=[TaskPackSummary.model_validate(p) for p in packs])


@router.get("/packs/{slug}", response_model=TaskPackDetail)
async def get_task_pack(slug: str, db: AsyncSession = Depends(get_db)) -> TaskPackDetail:
    result = await db.execute(select(TaskPack).where(TaskPack.slug == slug))
    pack = result.scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task pack '{slug}' not found")
    return TaskPackDetail.model_validate(pack)


@router.post("/score-session", response_model=GoldScoreResponse)
async def score_session_against_gold(
    body: GoldScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> GoldScoreResponse:
    """Compare this session's annotations to optional `gold` labels on each task."""
    try:
        session_id = UUID(body.session_id.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="session_id must be a valid UUID",
        ) from exc

    row = await db.get(WorkSession, session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if row.annotator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    tasks = row.tasks_json
    annotations = row.annotations_json if isinstance(row.annotations_json, dict) else {}
    return GoldScoringService().score_workspace(tasks, annotations)
