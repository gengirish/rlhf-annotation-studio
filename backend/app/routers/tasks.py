from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, TaskPack, WorkSession
from app.schemas.gold_scoring import GoldScoreRequest, GoldScoreResponse
from app.schemas.task_pack import (
    TaskPackCreate,
    TaskPackDetail,
    TaskPackListResponse,
    TaskPackSummary,
    TaskPackUpdate,
)
from app.schemas.task_validation import TaskValidationRequest, TaskValidationResponse
from app.services.gold_scoring_service import GoldScoringService
from app.services.task_validation_service import TaskValidationService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _raise_if_tasks_invalid(tasks_json: list[dict[str, Any]]) -> None:
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks_json)
    if invalid_rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Task validation failed",
                "issues": [i.model_dump() for i in issues],
            },
        )


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


@router.post("/packs", response_model=TaskPackDetail, status_code=status.HTTP_201_CREATED)
async def create_task_pack(
    body: TaskPackCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(get_current_user),
) -> TaskPackDetail:
    _raise_if_tasks_invalid(body.tasks_json)
    slug = body.slug.strip()
    existing = await db.execute(select(TaskPack).where(TaskPack.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task pack slug '{slug}' already exists",
        )
    pack = TaskPack(
        slug=slug,
        name=body.name.strip(),
        description=body.description or "",
        language=(body.language or "general").strip() or "general",
        task_count=len(body.tasks_json),
        tasks_json=body.tasks_json,
    )
    db.add(pack)
    await db.commit()
    await db.refresh(pack)
    return TaskPackDetail.model_validate(pack)


@router.put("/packs/{slug}", response_model=TaskPackDetail)
async def update_task_pack(
    slug: str,
    body: TaskPackUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(get_current_user),
) -> TaskPackDetail:
    result = await db.execute(select(TaskPack).where(TaskPack.slug == slug))
    pack = result.scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task pack '{slug}' not found")

    data = body.model_dump(exclude_unset=True)
    if "tasks_json" in data and data["tasks_json"] is not None:
        _raise_if_tasks_invalid(data["tasks_json"])
        pack.tasks_json = data["tasks_json"]
        pack.task_count = len(data["tasks_json"])

    if "slug" in data and data["slug"] is not None:
        new_slug = data["slug"].strip()
        if new_slug != pack.slug:
            clash = await db.execute(select(TaskPack).where(TaskPack.slug == new_slug))
            if clash.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Task pack slug '{new_slug}' already exists",
                )
            pack.slug = new_slug

    if "name" in data and data["name"] is not None:
        pack.name = data["name"].strip()
    if "description" in data and data["description"] is not None:
        pack.description = data["description"]
    if "language" in data and data["language"] is not None:
        pack.language = data["language"].strip() or "general"

    await db.commit()
    await db.refresh(pack)
    return TaskPackDetail.model_validate(pack)


@router.delete("/packs/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_pack(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(get_current_user),
) -> Response:
    result = await db.execute(select(TaskPack).where(TaskPack.slug == slug))
    pack = result.scalar_one_or_none()
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task pack '{slug}' not found")
    await db.delete(pack)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
