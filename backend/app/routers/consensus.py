from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_reviewer_or_admin
from app.db import get_db
from app.models.annotator import Annotator
from app.models.consensus import ConsensusConfig, ConsensusTask
from app.schemas.consensus import (
    AnnotatorNextTaskResponse,
    ConsensusConfigCreate,
    ConsensusConfigRead,
    ConsensusResolveRequest,
    ConsensusStatusResponse,
    ConsensusTaskRead,
    ConsensusTaskSubmit,
)
from app.services import consensus_service

router = APIRouter(prefix="/consensus", tags=["consensus"])


def _http_from_value_error(exc: ValueError) -> HTTPException:
    msg = str(exc)
    if "not found" in msg.lower():
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.post("/setup", response_model=ConsensusConfigRead, status_code=status.HTTP_201_CREATED)
async def setup_consensus(
    body: ConsensusConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> ConsensusConfigRead:
    try:
        cfg = await consensus_service.setup_consensus(db, body, current_user)
    except ValueError as exc:
        raise _http_from_value_error(exc) from exc
    return ConsensusConfigRead.model_validate(cfg)


@router.get("/config/{task_pack_id}", response_model=ConsensusConfigRead)
async def get_consensus_config(
    task_pack_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ConsensusConfigRead:
    result = await db.execute(
        select(ConsensusConfig).where(ConsensusConfig.task_pack_id == task_pack_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consensus config not found"
        )
    return ConsensusConfigRead.model_validate(cfg)


@router.get("/status/{task_pack_id}", response_model=ConsensusStatusResponse)
async def consensus_status(
    task_pack_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ConsensusStatusResponse:
    return await consensus_service.get_status(db, task_pack_id)


@router.get("/next/{task_pack_id}", response_model=AnnotatorNextTaskResponse)
async def next_consensus_task(
    task_pack_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> AnnotatorNextTaskResponse:
    try:
        nxt = await consensus_service.get_next_task(db, current_user.id, task_pack_id)
    except ValueError as exc:
        raise _http_from_value_error(exc) from exc
    if nxt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No consensus tasks available"
        )
    return nxt


@router.post("/tasks/{consensus_task_id}/submit", response_model=ConsensusTaskRead)
async def submit_consensus_annotation(
    consensus_task_id: UUID,
    body: ConsensusTaskSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ConsensusTaskRead:
    try:
        row = await consensus_service.submit_annotation(
            db,
            consensus_task_id,
            current_user.id,
            body.annotation,
        )
    except ValueError as exc:
        raise _http_from_value_error(exc) from exc
    return ConsensusTaskRead.model_validate(row)


@router.get("/tasks/{consensus_task_id}", response_model=ConsensusTaskRead)
async def get_consensus_task(
    consensus_task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ConsensusTaskRead:
    row = await db.get(ConsensusTask, consensus_task_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Consensus task not found"
        )

    aid = str(current_user.id)
    assigned = row.assigned_annotators or []
    is_assigned = aid in assigned
    is_reviewer = current_user.role in ("admin", "reviewer")

    if is_reviewer:
        return ConsensusTaskRead.model_validate(row)
    if is_assigned:
        return consensus_service.filter_task_read_for_annotator(row, current_user.id)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/tasks/{consensus_task_id}/resolve", response_model=ConsensusTaskRead)
async def resolve_consensus_task(
    consensus_task_id: UUID,
    body: ConsensusResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> ConsensusTaskRead:
    try:
        row = await consensus_service.resolve_dispute(
            db,
            consensus_task_id,
            current_user.id,
            body.resolved_annotation,
        )
    except ValueError as exc:
        raise _http_from_value_error(exc) from exc
    return ConsensusTaskRead.model_validate(row)


@router.get("/disputed/{task_pack_id}", response_model=list[ConsensusTaskRead])
async def list_disputed(
    task_pack_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> list[ConsensusTaskRead]:
    rows = await consensus_service.list_disputed_tasks(db, task_pack_id)
    return [ConsensusTaskRead.model_validate(r) for r in rows]
