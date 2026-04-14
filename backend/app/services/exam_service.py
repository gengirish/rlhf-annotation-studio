from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import ROLE_ADMIN, ROLE_REVIEWER
from app.models.annotator import Annotator
from app.models.exam import Exam, ExamAttempt, IntegrityEvent
from app.models.task_pack import TaskPack
from app.exam_rubric import rubric_rows_from_stored
from app.services.email_service import (
    send_exam_released_notification,
    send_exam_submitted_notification,
    send_review_queue_notification,
)
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
    RubricScoreRow,
)
from app.services.gold_scoring_service import GoldScoringService

STATUS_ACTIVE = "active"
STATUS_SUBMITTED = "submitted"
STATUS_TIMED_OUT = "timed_out"
STATUS_RELEASED = "released"

_SEVERITY_DELTA = {"info": 0.01, "warn": 0.05, "high": 0.15}


def _now() -> datetime:
    return datetime.now(UTC)


def _privileged(user: Annotator) -> bool:
    return user.role in (ROLE_ADMIN, ROLE_REVIEWER)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _apply_gold_to_attempt(attempt: ExamAttempt, exam: Exam) -> tuple[int, int]:
    """Sets attempt.score and attempt.passed from pack gold labels. Returns (total_gold, scored)."""
    pack = exam.task_pack
    tasks = pack.tasks_json if pack and isinstance(pack.tasks_json, list) else []
    answers = attempt.answers_json if isinstance(attempt.answers_json, dict) else {}
    gold = GoldScoringService().score_workspace(tasks, answers)
    attempt.score = gold.overall_accuracy
    if gold.total_gold_tasks <= 0:
        attempt.passed = None
    else:
        thr = float(exam.pass_threshold)
        attempt.passed = float(gold.overall_accuracy) >= thr
    return gold.total_gold_tasks, gold.scored_tasks


async def _get_exam_with_pack(db: AsyncSession, exam_id: UUID) -> Exam | None:
    result = await db.execute(select(Exam).options(selectinload(Exam.task_pack)).where(Exam.id == exam_id))
    return result.scalar_one_or_none()


async def _get_attempt_for_exam(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
) -> ExamAttempt | None:
    result = await db.execute(
        select(ExamAttempt)
        .options(selectinload(ExamAttempt.exam).selectinload(Exam.task_pack))
        .where(ExamAttempt.id == attempt_id)
        .where(ExamAttempt.exam_id == exam_id),
    )
    return result.scalar_one_or_none()


async def _reload_attempt(db: AsyncSession, attempt_id: UUID) -> ExamAttempt | None:
    res = await db.execute(
        select(ExamAttempt)
        .options(selectinload(ExamAttempt.exam).selectinload(Exam.task_pack))
        .where(ExamAttempt.id == attempt_id),
    )
    return res.scalar_one_or_none()


def _ensure_exam_attempt_match_or_404(attempt: ExamAttempt | None, exam_id: UUID) -> ExamAttempt:
    if attempt is None or attempt.exam_id != exam_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")
    return attempt


def _ensure_can_access_attempt(user: Annotator, attempt: ExamAttempt) -> None:
    if _privileged(user):
        return
    if attempt.annotator_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")


async def _apply_expiry_if_needed(db: AsyncSession, attempt: ExamAttempt) -> None:
    """If active and past expires_at, finalize as timed_out with scoring."""
    if attempt.status != STATUS_ACTIVE:
        return
    if _now() < attempt.expires_at:
        return
    exam = attempt.exam
    if exam is None:
        result = await _get_exam_with_pack(db, attempt.exam_id)
        if result is None:
            return
        attempt.exam = result
        exam = result
    attempt.status = STATUS_TIMED_OUT
    attempt.submitted_at = attempt.expires_at
    _apply_gold_to_attempt(attempt, exam)


async def create_exam(db: AsyncSession, body: ExamCreate, creator: Annotator) -> Exam:
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task pack not found")
    row = Exam(
        title=body.title.strip(),
        description=body.description or "",
        task_pack_id=body.task_pack_id,
        duration_minutes=body.duration_minutes,
        pass_threshold=float(body.pass_threshold),
        max_attempts=body.max_attempts,
        is_published=body.is_published,
        created_by=creator.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_exams(db: AsyncSession, user: Annotator) -> list[Exam]:
    q = select(Exam).order_by(Exam.created_at.desc())
    if not _privileged(user):
        q = q.where(Exam.is_published.is_(True))
    result = await db.execute(q)
    return list(result.scalars().all())


async def start_or_resume_attempt(db: AsyncSession, exam_id: UUID, user: Annotator) -> ExamAttempt:
    exam = await _get_exam_with_pack(db, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    if not exam.is_published and not _privileged(user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")

    result = await db.execute(
        select(ExamAttempt)
        .options(selectinload(ExamAttempt.exam).selectinload(Exam.task_pack))
        .where(ExamAttempt.exam_id == exam_id)
        .where(ExamAttempt.annotator_id == user.id)
        .where(ExamAttempt.status == STATUS_ACTIVE),
    )
    active = result.scalar_one_or_none()
    if active is not None:
        await _apply_expiry_if_needed(db, active)
        if active.status == STATUS_ACTIVE:
            await db.commit()
            await db.refresh(active)
            return active
        await db.commit()

    n_result = await db.execute(
        select(sa_func.count()).select_from(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.annotator_id == user.id,
        ),
    )
    n_attempts = int(n_result.scalar_one() or 0)
    if n_attempts >= exam.max_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum exam attempts reached for this user",
        )

    started = _now()
    row = ExamAttempt(
        exam_id=exam.id,
        annotator_id=user.id,
        started_at=started,
        expires_at=started + timedelta(minutes=exam.duration_minutes),
        status=STATUS_ACTIVE,
        answers_json={},
        task_times_json={},
        integrity_score=1.0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    row.exam = exam
    return row


async def get_attempt(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
    user: Annotator,
) -> ExamAttempt:
    attempt = _ensure_exam_attempt_match_or_404(await _get_attempt_for_exam(db, exam_id, attempt_id), exam_id)
    _ensure_can_access_attempt(user, attempt)
    await _apply_expiry_if_needed(db, attempt)
    await db.commit()
    attempt = await _reload_attempt(db, attempt_id) or attempt
    return attempt


async def save_answer(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
    user: Annotator,
    body: ExamAnswerSave,
) -> ExamAttempt:
    attempt = _ensure_exam_attempt_match_or_404(await _get_attempt_for_exam(db, exam_id, attempt_id), exam_id)
    if attempt.annotator_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")
    await _apply_expiry_if_needed(db, attempt)
    if attempt.status != STATUS_ACTIVE:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot save answers on a finalized attempt",
        )
    answers = dict(attempt.answers_json) if isinstance(attempt.answers_json, dict) else {}
    answers[body.task_id] = body.annotation_json
    attempt.answers_json = answers
    if body.time_spent_seconds is not None:
        times = dict(attempt.task_times_json) if isinstance(attempt.task_times_json, dict) else {}
        prev = times.get(body.task_id)
        prev_f = float(prev) if isinstance(prev, (int, float)) else 0.0
        times[body.task_id] = prev_f + float(body.time_spent_seconds)
        attempt.task_times_json = times
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def log_integrity_event(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
    user: Annotator,
    body: IntegrityEventCreate,
) -> IntegrityEventRead:
    attempt = _ensure_exam_attempt_match_or_404(await _get_attempt_for_exam(db, exam_id, attempt_id), exam_id)
    if attempt.annotator_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")
    await _apply_expiry_if_needed(db, attempt)
    if attempt.status != STATUS_ACTIVE:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot log integrity events on a finalized attempt",
        )
    ev = IntegrityEvent(
        attempt_id=attempt.id,
        event_type=body.event_type.strip(),
        severity=body.severity,
        payload_json=body.payload_json if isinstance(body.payload_json, dict) else {},
    )
    db.add(ev)
    delta = _SEVERITY_DELTA.get(body.severity, 0.0)
    attempt.integrity_score = _clamp01(float(attempt.integrity_score) - delta)
    await db.commit()
    await db.refresh(ev)
    return IntegrityEventRead.model_validate(ev)


def _notify_reviewers_of_submission(
    db: AsyncSession,
    annotator_name: str,
    exam_title: str,
) -> None:
    """Best-effort notification to admins/reviewers. Sync call, failures logged."""
    import asyncio

    async def _inner() -> None:
        result = await db.execute(
            select(Annotator).where(Annotator.role.in_((ROLE_ADMIN, ROLE_REVIEWER))),
        )
        reviewers = list(result.scalars().all())
        for rev in reviewers:
            try:
                send_review_queue_notification(
                    reviewer_email=rev.email,
                    reviewer_name=rev.name,
                    annotator_name=annotator_name,
                    exam_title=exam_title,
                )
            except Exception:
                pass

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_inner())
    except RuntimeError:
        pass


async def submit_attempt(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
    user: Annotator,
) -> ExamAttempt:
    attempt = _ensure_exam_attempt_match_or_404(await _get_attempt_for_exam(db, exam_id, attempt_id), exam_id)
    if attempt.annotator_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")
    exam = attempt.exam
    if exam is None:
        exam = await _get_exam_with_pack(db, exam_id)
        if exam is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
        attempt.exam = exam

    await _apply_expiry_if_needed(db, attempt)
    if attempt.status != STATUS_ACTIVE:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attempt is not active or timer has expired",
        )

    attempt.status = STATUS_SUBMITTED
    attempt.submitted_at = _now()
    _apply_gold_to_attempt(attempt, exam)
    await db.commit()
    await db.refresh(attempt)

    try:
        send_exam_submitted_notification(
            annotator_email=user.email,
            annotator_name=user.name,
            exam_title=exam.title,
            score=attempt.score,
            passed=attempt.passed,
        )
        _notify_reviewers_of_submission(db, user.name, exam.title)
    except Exception:
        pass

    return attempt


async def read_result(
    db: AsyncSession,
    exam_id: UUID,
    attempt_id: UUID,
    user: Annotator,
) -> ExamResultRead:
    attempt = _ensure_exam_attempt_match_or_404(await _get_attempt_for_exam(db, exam_id, attempt_id), exam_id)
    _ensure_can_access_attempt(user, attempt)
    await _apply_expiry_if_needed(db, attempt)
    await db.commit()
    attempt = await _reload_attempt(db, attempt_id) or attempt

    if not _privileged(user) and attempt.annotator_id == user.id and attempt.status != STATUS_RELEASED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Results are not available until released by a reviewer",
        )

    exam = attempt.exam
    if exam is None:
        exam = await _get_exam_with_pack(db, exam_id)
    total_gold = 0
    scored = 0
    if exam and exam.task_pack:
        tasks = exam.task_pack.tasks_json if isinstance(exam.task_pack.tasks_json, list) else []
        gold = GoldScoringService().score_workspace(tasks, attempt.answers_json if isinstance(attempt.answers_json, dict) else {})
        total_gold = gold.total_gold_tasks
        scored = gold.scored_tasks

    rubric_raw = attempt.review_rubric_scores_json if isinstance(attempt.review_rubric_scores_json, dict) else {}
    rubric = [RubricScoreRow(**r) for r in rubric_rows_from_stored(rubric_raw)]

    return ExamResultRead(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status,
        score=attempt.score,
        passed=attempt.passed,
        integrity_score=float(attempt.integrity_score),
        submitted_at=attempt.submitted_at,
        released_at=attempt.released_at,
        review_notes=attempt.review_notes,
        total_gold_tasks=total_gold,
        scored_tasks=scored,
        rubric=rubric,
    )


async def list_review_attempts(db: AsyncSession) -> list[ReviewAttemptSummary]:
    q = (
        select(ExamAttempt, Exam, Annotator)
        .join(Exam, Exam.id == ExamAttempt.exam_id)
        .join(Annotator, Annotator.id == ExamAttempt.annotator_id)
        .where(ExamAttempt.status.in_((STATUS_SUBMITTED, STATUS_TIMED_OUT)))
        .order_by(ExamAttempt.submitted_at.asc().nullsfirst(), ExamAttempt.started_at.asc())
    )
    result = await db.execute(q)
    rows = result.all()
    out: list[ReviewAttemptSummary] = []
    for att, ex, ann in rows:
        raw_rubric = att.review_rubric_scores_json if isinstance(att.review_rubric_scores_json, dict) else {}
        rubric_scores = {k: v for k, v in raw_rubric.items() if isinstance(v, int) and not isinstance(v, bool)}
        out.append(
            ReviewAttemptSummary(
                id=att.id,
                exam_id=att.exam_id,
                exam_title=ex.title,
                annotator_id=att.annotator_id,
                annotator_email=ann.email,
                started_at=att.started_at,
                expires_at=att.expires_at,
                submitted_at=att.submitted_at,
                status=att.status,
                score=att.score,
                passed=att.passed,
                integrity_score=float(att.integrity_score),
                review_notes=att.review_notes,
                released_at=att.released_at,
                review_rubric_scores=rubric_scores,
            ),
        )
    return out


async def release_attempt(
    db: AsyncSession,
    attempt_id: UUID,
    reviewer: Annotator,
    body: ReviewReleaseRequest,
) -> ExamAttempt:
    result = await db.execute(
        select(ExamAttempt)
        .options(selectinload(ExamAttempt.exam).selectinload(Exam.task_pack))
        .where(ExamAttempt.id == attempt_id),
    )
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam attempt not found")

    if attempt.status == STATUS_RELEASED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attempt already released")
    if attempt.status not in (STATUS_SUBMITTED, STATUS_TIMED_OUT):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted or timed-out attempts can be released",
        )

    if not body.release:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="release must be true")

    attempt.status = STATUS_RELEASED
    attempt.released_at = _now()
    attempt.released_by = reviewer.id
    if body.review_notes is not None:
        attempt.review_notes = body.review_notes.strip() or None
    if body.review_rubric_scores is not None:
        attempt.review_rubric_scores_json = body.review_rubric_scores

    await db.commit()
    await db.refresh(attempt)

    try:
        ann_result = await db.execute(
            select(Annotator).where(Annotator.id == attempt.annotator_id),
        )
        ann = ann_result.scalar_one_or_none()
        exam = attempt.exam
        exam_title = exam.title if exam else "Exam"
        if ann:
            send_exam_released_notification(
                annotator_email=ann.email,
                annotator_name=ann.name,
                exam_title=exam_title,
                score=attempt.score,
                passed=attempt.passed,
                review_notes=attempt.review_notes,
            )
    except Exception:
        pass

    return attempt


def to_exam_read(row: Exam) -> ExamRead:
    return ExamRead.model_validate(row)


def to_attempt_start(row: ExamAttempt) -> ExamAttemptStartResponse:
    return ExamAttemptStartResponse.model_validate(row)


def to_attempt_read(row: ExamAttempt) -> ExamAttemptRead:
    return ExamAttemptRead.model_validate(row)


def to_submit_response(row: ExamAttempt) -> ExamAttemptSubmitResponse:
    return ExamAttemptSubmitResponse.model_validate(row)


def to_release_response(row: ExamAttempt) -> ReviewReleaseResponse:
    raw = row.review_rubric_scores_json if isinstance(row.review_rubric_scores_json, dict) else {}
    rubric_scores = {k: v for k, v in raw.items() if isinstance(v, int) and not isinstance(v, bool)}
    return ReviewReleaseResponse(
        id=row.id,
        exam_id=row.exam_id,
        status=row.status,
        released_at=row.released_at,
        released_by=row.released_by,
        review_notes=row.review_notes,
        review_rubric_scores=rubric_scores,
    )
