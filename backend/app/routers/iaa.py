from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_reviewer_or_admin
from app.db import get_db
from app.models.annotator import Annotator
from app.models.iaa_result import IAAResult
from app.models.review_assignment import ReviewAssignment
from app.models.task_pack import TaskPack
from app.schemas.iaa import IAARequest, IAAResponse
from app.services.iaa_service import IAAService

router = APIRouter(prefix="/iaa", tags=["iaa"])

STATUS_SUBMITTED = "submitted"


def _assignments_to_annotation_dicts(rows: list[ReviewAssignment]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        payload = row.annotation_json if isinstance(row.annotation_json, dict) else {}
        pref = payload.get("preference")
        dims = payload.get("dimensions")
        out.append(
            {
                "annotator_id": row.annotator_id,
                "task_id": row.task_id,
                "preference": pref if isinstance(pref, int) else None,
                "dimensions": dims if isinstance(dims, dict) else {},
            },
        )
    return out


@router.post("/compute", response_model=IAAResponse)
async def compute_iaa(
    body: IAARequest,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(require_reviewer_or_admin),
) -> IAAResponse:
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")

    q = (
        select(ReviewAssignment)
        .where(ReviewAssignment.task_pack_id == body.task_pack_id)
        .where(ReviewAssignment.status == STATUS_SUBMITTED)
        .where(ReviewAssignment.annotation_json.is_not(None))
    )
    result = await db.execute(q)
    assignments = list(result.scalars().all())

    raw = _assignments_to_annotation_dicts(assignments)
    response = IAAService.compute_from_annotations(
        raw,
        task_pack_id=body.task_pack_id,
        task_ids=body.task_ids,
    )

    cache_row = IAAResult(
        task_pack_id=body.task_pack_id,
        result_json=response.model_dump(mode="json"),
        n_annotators=response.n_annotators,
        overall_kappa=response.overall_kappa,
        overall_alpha=response.overall_alpha,
        computed_at=response.computed_at,
    )
    db.add(cache_row)
    await db.commit()

    return response


@router.get("/summary/{task_pack_id}", response_model=IAAResponse)
async def iaa_summary(
    task_pack_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _current_user: Annotator = Depends(require_reviewer_or_admin),
) -> IAAResponse:
    pack = await db.get(TaskPack, task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")

    q = (
        select(IAAResult)
        .where(IAAResult.task_pack_id == task_pack_id)
        .order_by(desc(IAAResult.computed_at))
        .limit(1)
    )
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cached IAA result for this task pack; call POST /iaa/compute first",
        )
    return IAAResponse.model_validate(row.result_json)
