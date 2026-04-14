from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin, require_reviewer_or_admin
from app.db import get_db
from app.models import Annotator
from app.exam_rubric import EXAM_REVIEW_RUBRIC_CRITERIA
from app.schemas.exam import (
    ExamAnswerSave,
    ExamAttemptRead,
    ExamAttemptStartResponse,
    ExamAttemptSubmitResponse,
    ExamCreate,
    ExamRead,
    ExamResultRead,
    IntegrityEventCreate,
    IntegrityEventRead,
    ReviewAttemptSummary,
    ReviewReleaseRequest,
    ReviewReleaseResponse,
    RubricCriterionRead,
)
from app.services import exam_service

router = APIRouter(prefix="/exams", tags=["exams"])


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
async def create_exam(
    body: ExamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_admin),
) -> ExamRead:
    row = await exam_service.create_exam(db, body, current_user)
    return exam_service.to_exam_read(row)


@router.get("", response_model=list[ExamRead])
async def list_exams(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[ExamRead]:
    rows = await exam_service.list_exams(db, current_user)
    return [exam_service.to_exam_read(r) for r in rows]


@router.get("/review/rubric-criteria", response_model=list[RubricCriterionRead])
async def list_rubric_criteria() -> list[RubricCriterionRead]:
    return [RubricCriterionRead.model_validate(c) for c in EXAM_REVIEW_RUBRIC_CRITERIA]


@router.get("/review/attempts", response_model=list[ReviewAttemptSummary])
async def list_attempts_for_review(
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(require_reviewer_or_admin),
) -> list[ReviewAttemptSummary]:
    return await exam_service.list_review_attempts(db)


@router.post(
    "/review/attempts/{attempt_id}/release",
    response_model=ReviewReleaseResponse,
)
async def release_attempt_review(
    attempt_id: UUID,
    body: ReviewReleaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(require_reviewer_or_admin),
) -> ReviewReleaseResponse:
    row = await exam_service.release_attempt(db, attempt_id, current_user, body)
    return exam_service.to_release_response(row)


@router.post(
    "/{exam_id}/attempts/start",
    response_model=ExamAttemptStartResponse,
)
async def start_or_resume_attempt(
    exam_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ExamAttemptStartResponse:
    row = await exam_service.start_or_resume_attempt(db, exam_id, current_user)
    return exam_service.to_attempt_start(row)


@router.get("/{exam_id}/attempts/{attempt_id}", response_model=ExamAttemptRead)
async def get_attempt(
    exam_id: UUID,
    attempt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ExamAttemptRead:
    row = await exam_service.get_attempt(db, exam_id, attempt_id, current_user)
    return exam_service.to_attempt_read(row)


@router.put("/{exam_id}/attempts/{attempt_id}/answer", response_model=ExamAttemptRead)
async def save_answer(
    exam_id: UUID,
    attempt_id: UUID,
    body: ExamAnswerSave,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ExamAttemptRead:
    row = await exam_service.save_answer(db, exam_id, attempt_id, current_user, body)
    return exam_service.to_attempt_read(row)


@router.post(
    "/{exam_id}/attempts/{attempt_id}/integrity-events",
    response_model=IntegrityEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_integrity_event(
    exam_id: UUID,
    attempt_id: UUID,
    body: IntegrityEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> IntegrityEventRead:
    return await exam_service.log_integrity_event(db, exam_id, attempt_id, current_user, body)


@router.post(
    "/{exam_id}/attempts/{attempt_id}/submit",
    response_model=ExamAttemptSubmitResponse,
)
async def submit_attempt(
    exam_id: UUID,
    attempt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ExamAttemptSubmitResponse:
    row = await exam_service.submit_attempt(db, exam_id, attempt_id, current_user)
    return exam_service.to_submit_response(row)


@router.get("/{exam_id}/attempts/{attempt_id}/result", response_model=ExamResultRead)
async def get_attempt_result(
    exam_id: UUID,
    attempt_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> ExamResultRead:
    return await exam_service.read_result(db, exam_id, attempt_id, current_user)
