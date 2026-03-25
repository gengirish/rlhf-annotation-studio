from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.task_pack import TaskPack
from app.schemas.task_pack import TaskPackDetail, TaskPackListResponse, TaskPackSummary
from app.schemas.task_validation import TaskValidationRequest, TaskValidationResponse
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
