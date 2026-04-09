from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_or_api_key
from app.db import get_db
from app.models import Annotator, TaskPack, WorkSession
from app.schemas.gold_scoring import GoldScoreRequest, GoldScoreResponse
from app.schemas.task_pack import (
    TaskPackCreate,
    TaskPackDetail,
    TaskPackListResponse,
    TaskPackSummary,
    TaskPackUpdate,
    TaskSearchHit,
    TaskSearchResponse,
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
async def list_task_packs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TaskPackListResponse:
    total_result = await db.execute(select(func.count(TaskPack.id)))
    total = int(total_result.scalar_one() or 0)

    result = await db.execute(
        select(TaskPack).order_by(TaskPack.name, TaskPack.slug).limit(limit).offset(offset)
    )
    packs = result.scalars().all()
    return TaskPackListResponse(
        packs=[TaskPackSummary.model_validate(p) for p in packs],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(packs)) < total,
    )


@router.get("/search", response_model=TaskSearchResponse)
async def search_tasks(
    q: str = Query(default="", max_length=200),
    language: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> TaskSearchResponse:
    query = q.strip()
    if not query:
        return TaskSearchResponse(packs=[], tasks=[], query=q, total_packs=0, total_tasks=0)

    pattern = f"%{query.lower()}%"

    pack_stmt = select(TaskPack).where(
        or_(
            func.lower(TaskPack.name).like(pattern),
            func.lower(TaskPack.slug).like(pattern),
            func.lower(TaskPack.description).like(pattern),
        )
    )
    if language:
        pack_stmt = pack_stmt.where(func.lower(TaskPack.language) == language.strip().lower())
    pack_result = await db.execute(pack_stmt.order_by(TaskPack.name, TaskPack.slug).limit(limit))
    pack_rows = pack_result.scalars().all()

    task_stmt = select(TaskPack).where(
        func.lower(cast(TaskPack.tasks_json, String)).like(pattern)
    )
    if language:
        task_stmt = task_stmt.where(func.lower(TaskPack.language) == language.strip().lower())
    task_pack_result = await db.execute(task_stmt.order_by(TaskPack.name, TaskPack.slug))
    task_pack_rows = task_pack_result.scalars().all()

    q_lower = query.lower()
    task_type_lower = task_type.strip().lower() if task_type else None
    task_hits: list[TaskSearchHit] = []
    for pack in task_pack_rows:
        for idx, task in enumerate(pack.tasks_json or []):
            title = (task.get("title") or "").lower()
            task_id = (task.get("id") or "").lower()
            prompt = (task.get("prompt") or "").lower()
            t_type = (task.get("type") or "").lower()
            if q_lower not in title and q_lower not in task_id and q_lower not in prompt:
                continue
            if task_type_lower and t_type != task_type_lower:
                continue
            task_hits.append(TaskSearchHit(
                pack_slug=pack.slug,
                pack_name=pack.name,
                language=pack.language,
                task_id=task.get("id", ""),
                task_title=task.get("title", ""),
                task_type=task.get("type", ""),
                task_index=idx,
            ))

    total_tasks = len(task_hits)
    task_hits = task_hits[:limit]

    return TaskSearchResponse(
        packs=[TaskPackSummary.model_validate(p) for p in pack_rows],
        tasks=task_hits,
        query=q,
        total_packs=len(pack_rows),
        total_tasks=total_tasks,
    )


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
    _current_user: Annotator = Depends(get_current_user_or_api_key),
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
    _current_user: Annotator = Depends(get_current_user_or_api_key),
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
    _current_user: Annotator = Depends(get_current_user_or_api_key),
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
    current_user: Annotator = Depends(get_current_user_or_api_key),
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
