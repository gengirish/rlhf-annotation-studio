from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_reviewer_or_admin
from app.db import get_db
from app.models import Annotator, ReviewAssignment, TaskPack
from app.schemas.review_assignment import (
    BulkAssignRequest,
    ReviewAssignmentRead,
    ReviewAssignmentUpdate,
    ReviewAssignRequest,
    ReviewSubmitRequest,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])

STATUS_SUBMITTED = "submitted"


@router.post("/assign", response_model=ReviewAssignmentRead, status_code=status.HTTP_201_CREATED)
async def assign_review(
    body: ReviewAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> ReviewAssignmentRead:
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    assignee = await db.get(Annotator, body.annotator_id)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotator not found")

    existing = await db.execute(
        select(ReviewAssignment)
        .where(ReviewAssignment.task_pack_id == body.task_pack_id)
        .where(ReviewAssignment.task_id == body.task_id)
        .where(ReviewAssignment.annotator_id == body.annotator_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task is already assigned to this annotator",
        )

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
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> list[ReviewAssignmentRead]:
    q = select(ReviewAssignment).where(ReviewAssignment.status == STATUS_SUBMITTED)
    if current_user.org_id is not None:
        q = q.join(Annotator, ReviewAssignment.annotator_id == Annotator.id).where(
            Annotator.org_id == current_user.org_id
        )
    q = q.order_by(ReviewAssignment.updated_at.asc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [ReviewAssignmentRead.model_validate(r) for r in rows]


@router.get("/team", response_model=list[ReviewAssignmentRead])
async def list_team_reviews(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
    status_filter: str | None = Query(None, alias="status"),
    annotator_id: str | None = Query(None),
) -> list[ReviewAssignmentRead]:
    q = select(ReviewAssignment)
    if current_user.org_id is not None:
        q = q.join(Annotator, ReviewAssignment.annotator_id == Annotator.id).where(
            Annotator.org_id == current_user.org_id
        )
    if status_filter is not None and status_filter.strip():
        q = q.where(ReviewAssignment.status == status_filter.strip())
    if annotator_id is not None and annotator_id.strip():
        try:
            aid = UUID(annotator_id.strip())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid annotator_id",
            ) from exc
        q = q.where(ReviewAssignment.annotator_id == aid)
    q = q.order_by(ReviewAssignment.created_at.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [ReviewAssignmentRead.model_validate(r) for r in rows]


@router.post(
    "/bulk-assign",
    response_model=list[ReviewAssignmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def bulk_assign_reviews(
    body: BulkAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> list[ReviewAssignmentRead]:
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    assignee = await db.get(Annotator, body.annotator_id)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotator not found")

    existing_result = await db.execute(
        select(ReviewAssignment.task_id)
        .where(ReviewAssignment.task_pack_id == body.task_pack_id)
        .where(ReviewAssignment.annotator_id == body.annotator_id)
    )
    existing_task_ids = set(existing_result.scalars().all())

    created: list[ReviewAssignment] = []
    for task in pack.tasks_json or []:
        tid = task.get("id") if isinstance(task, dict) else None
        if not tid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task pack contains a task without id",
            )
        if str(tid) in existing_task_ids:
            continue
        row = ReviewAssignment(
            task_pack_id=body.task_pack_id,
            task_id=str(tid),
            annotator_id=body.annotator_id,
            status="assigned",
        )
        db.add(row)
        created.append(row)
        existing_task_ids.add(str(tid))

    await db.commit()
    for row in created:
        await db.refresh(row)
    return [ReviewAssignmentRead.model_validate(r) for r in created]


@router.put("/{assignment_id}", response_model=ReviewAssignmentRead)
async def update_review_assignment(
    assignment_id: UUID,
    body: ReviewAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> ReviewAssignmentRead:
    row = await db.get(ReviewAssignment, assignment_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if current_user.org_id is not None:
        assignee = await db.get(Annotator, row.annotator_id)
        if assignee is None or assignee.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assignment belongs to a different organization",
            )

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
