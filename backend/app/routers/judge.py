from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_or_api_key, require_reviewer_or_admin
from app.config import get_settings
from app.db import get_db
from app.models.annotator import Annotator
from app.models.llm_evaluation import LLMEvaluation
from app.models.task_pack import TaskPack
from app.schemas.llm_judge import (
    EvaluationRead,
    HumanOverrideRequest,
    JudgeBatchResponse,
    JudgeTaskRequest,
)
from app.services.llm_judge_service import apply_human_override, evaluate_batch

router = APIRouter(prefix="/judge", tags=["judge"])


@router.post("/evaluate", response_model=JudgeBatchResponse)
async def judge_evaluate(
    body: JudgeTaskRequest,
    db: AsyncSession = Depends(get_db),
    _reviewer: Annotator = Depends(require_reviewer_or_admin),
) -> JudgeBatchResponse:
    settings = get_settings()
    if not settings.inference_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inference is disabled",
        )
    try:
        return await evaluate_batch(db, body, settings)
    except ValueError as exc:
        if str(exc) == "Task pack not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task pack not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.get("/evaluations/{task_pack_id}", response_model=list[EvaluationRead])
async def list_evaluations_for_pack(
    task_pack_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(get_current_user_or_api_key),
) -> list[EvaluationRead]:
    pack = await db.get(TaskPack, task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    result = await db.execute(
        select(LLMEvaluation)
        .where(LLMEvaluation.task_pack_id == task_pack_id)
        .order_by(LLMEvaluation.created_at.desc()),
    )
    rows = result.scalars().all()
    return [EvaluationRead.model_validate(r) for r in rows]


@router.get("/evaluations/{task_pack_id}/{task_id}", response_model=EvaluationRead)
async def get_evaluation_for_task(
    task_pack_id: UUID,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(get_current_user_or_api_key),
) -> EvaluationRead:
    pack = await db.get(TaskPack, task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    result = await db.execute(
        select(LLMEvaluation)
        .where(LLMEvaluation.task_pack_id == task_pack_id)
        .where(LLMEvaluation.task_id == task_id)
        .order_by(LLMEvaluation.updated_at.desc())
        .limit(1),
    )
    row = result.scalars().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return EvaluationRead.model_validate(row)


@router.post("/evaluations/{evaluation_id}/override", response_model=EvaluationRead)
async def override_evaluation(
    evaluation_id: UUID,
    body: HumanOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user_or_api_key),
) -> EvaluationRead:
    if body.preference is None and body.dimensions is None and body.reasoning is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of preference, dimensions, or reasoning must be set",
        )
    row = await apply_human_override(db, evaluation_id, current_user, body)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    return EvaluationRead.model_validate(row)


@router.post("/evaluations/{evaluation_id}/accept", response_model=EvaluationRead)
async def accept_evaluation(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(get_current_user_or_api_key),
) -> EvaluationRead:
    row = await db.get(LLMEvaluation, evaluation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    row.status = "accepted"
    await db.commit()
    await db.refresh(row)
    return EvaluationRead.model_validate(row)


@router.post("/evaluations/{evaluation_id}/reject", response_model=EvaluationRead)
async def reject_evaluation(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(get_current_user_or_api_key),
) -> EvaluationRead:
    row = await db.get(LLMEvaluation, evaluation_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation not found")
    row.status = "rejected"
    await db.commit()
    await db.refresh(row)
    return EvaluationRead.model_validate(row)
