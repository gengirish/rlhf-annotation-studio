from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    get_current_user,
    require_admin,
    require_reviewer_or_admin,
)
from app.db import get_db
from app.models.annotator import Annotator
from app.models.quality_score import CalibrationTest
from app.schemas.quality import (
    CalibrationAttemptRead,
    CalibrationAttemptResult,
    CalibrationAttemptSubmit,
    CalibrationTestCreate,
    CalibrationTestRead,
    QualityDashboard,
    QualityDriftAlert,
    QualityLeaderboard,
    QualityScoreRead,
)
from app.services.quality_service import QualityService

router = APIRouter(prefix="/quality", tags=["quality"])


def _require_org(user: Annotator) -> uuid.UUID:
    if user.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not assigned to an organization",
        )
    return user.org_id


@router.get("/score/{annotator_id}", response_model=QualityScoreRead)
async def get_quality_score(
    annotator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    task_pack_id: uuid.UUID | None = Query(None),
) -> QualityScoreRead:
    if current_user.role not in (ROLE_ADMIN, ROLE_REVIEWER):
        if current_user.id != annotator_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    svc = QualityService(db)
    existing = await svc.latest_score_read(annotator_id, task_pack_id=task_pack_id)
    if existing is not None:
        return existing
    return await svc.compute_annotator_score(annotator_id, task_pack_id=task_pack_id)


@router.get("/leaderboard", response_model=QualityLeaderboard)
async def get_quality_leaderboard(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> QualityLeaderboard:
    org_id = _require_org(current_user)
    return await QualityService(db).compute_leaderboard(org_id)


@router.get("/dashboard", response_model=QualityDashboard)
async def get_quality_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
) -> QualityDashboard:
    org_id = _require_org(current_user)
    return await QualityService(db).build_dashboard(org_id)


@router.get("/drift/{annotator_id}", response_model=list[QualityDriftAlert])
async def get_quality_drift(
    annotator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
    window_days: int = Query(7, ge=1, le=90),
) -> list[QualityDriftAlert]:
    _require_org(current_user)
    return await QualityService(db).detect_drift(annotator_id, window_days=window_days)


@router.post(
    "/calibration", response_model=CalibrationTestRead, status_code=status.HTTP_201_CREATED
)
async def create_calibration(
    body: CalibrationTestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
) -> CalibrationTestRead:
    _require_org(current_user)
    svc = QualityService(db)
    try:
        row = await svc.create_calibration_test(body, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return CalibrationTestRead.model_validate(row)


@router.get("/calibration", response_model=list[CalibrationTestRead])
async def list_calibration_tests(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[CalibrationTestRead]:
    org_id = current_user.org_id
    rows = await QualityService(db).list_calibration_tests_for_org(org_id)
    return [CalibrationTestRead.model_validate(r) for r in rows]


@router.post("/calibration/{test_id}/attempt", response_model=CalibrationAttemptResult)
async def submit_calibration_attempt(
    test_id: uuid.UUID,
    body: CalibrationAttemptSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> CalibrationAttemptResult:
    svc = QualityService(db)
    try:
        attempt, passed = await svc.attempt_calibration(
            test_id,
            current_user.id,
            body.annotations,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return CalibrationAttemptResult(
        passed=passed,
        attempt=CalibrationAttemptRead.model_validate(attempt),
    )


@router.get("/calibration/{test_id}/results", response_model=list[CalibrationAttemptRead])
async def list_calibration_results(
    test_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> list[CalibrationAttemptRead]:
    if await db.get(CalibrationTest, test_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calibration test not found"
        )
    attempts = await QualityService(db).calibration_attempts_for_test(test_id)
    return [CalibrationAttemptRead.model_validate(a) for a in attempts]


@router.post("/recompute/{annotator_id}", response_model=QualityScoreRead)
async def recompute_quality_scores(
    annotator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
    task_pack_id: uuid.UUID | None = Query(None),
) -> QualityScoreRead:
    _ = current_user
    svc = QualityService(db)
    try:
        return await svc.compute_annotator_score(annotator_id, task_pack_id=task_pack_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
