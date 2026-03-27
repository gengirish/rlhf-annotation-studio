from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, ReviewAssignment, TaskPack
from app.schemas.review_assignment import (
    ReviewAssignRequest,
    ReviewAssignmentRead,
    ReviewAssignmentUpdate,
    ReviewSubmitRequest,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])

STATUS_SUBMITTED = "submitted"


@router.post("/assign", response_model=ReviewAssignmentRead, status_code=status.HTTP_201_CREATED)
async def assign_review(
    body: ReviewAssignRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(get_current_user),
) -> ReviewAssignmentRead:
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    assignee = await db.get(Annotator, body.annotator_id)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotator not found")

    row = ReviewAssignment(
        task_pack_id=body.task_pack_id,
        task_id=body.task_id,
        annotator_id=body.annotator_id,
        status="assigned",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return ReviewAssignmentRead.model_validate(row)


@router.get("/queue", response_model=list[ReviewAssignmentRead])
async def list_my_review_queue(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    status_filter: str | None = Query(None, alias="status"),
) -> list[ReviewAssignmentRead]:
    q = select(ReviewAssignment).where(ReviewAssignment.annotator_id == current_user.id)
    if status_filter is not None and status_filter.strip():
        q = q.where(ReviewAssignment.status == status_filter.strip())
    q = q.order_by(ReviewAssignment.created_at.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [ReviewAssignmentRead.model_validate(r) for r in rows]


@router.get("/pending", response_model=list[ReviewAssignmentRead])
async def list_pending_reviews(
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(get_current_user),
) -> list[ReviewAssignmentRead]:
    result = await db.execute(
        select(ReviewAssignment)
        .where(ReviewAssignment.status == STATUS_SUBMITTED)
        .order_by(ReviewAssignment.updated_at.asc())
    )
    rows = result.scalars().all()
    return [ReviewAssignmentRead.model_validate(r) for r in rows]


@router.put("/{assignment_id}", response_model=ReviewAssignmentRead)
async def update_review_assignment(
    assignment_id: UUID,
    body: ReviewAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ReviewAssignmentRead:
    row = await db.get(ReviewAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    row.status = body.status.strip()
    row.reviewer_notes = body.reviewer_notes
    row.reviewer_id = current_user.id

    await db.commit()
    await db.refresh(row)
    return ReviewAssignmentRead.model_validate(row)


@router.post("/{assignment_id}/submit", response_model=ReviewAssignmentRead)
async def submit_review_annotation(
    assignment_id: UUID,
    body: ReviewSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ReviewAssignmentRead:
    row = await db.get(ReviewAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if row.annotator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    row.annotation_json = dict(body.annotation_json) if body.annotation_json else {}
    row.status = STATUS_SUBMITTED

    await db.commit()
    await db.refresh(row)
    return ReviewAssignmentRead.model_validate(row)
