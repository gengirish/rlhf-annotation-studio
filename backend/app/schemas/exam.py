from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExamAttemptStatus = Literal["active", "submitted", "timed_out", "released"]
IntegritySeverity = Literal["info", "warn", "high"]


class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    task_pack_id: UUID
    duration_minutes: int = Field(ge=1, le=24 * 60)
    pass_threshold: float = Field(ge=0.0, le=1.0)
    max_attempts: int = Field(ge=1, le=100)
    is_published: bool = False


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    task_pack_id: UUID
    duration_minutes: int
    pass_threshold: float
    max_attempts: int
    is_published: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ExamAttemptStartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    annotator_id: UUID
    started_at: datetime
    expires_at: datetime
    status: str
    answers_json: dict[str, Any]
    task_times_json: dict[str, Any]
    integrity_score: float


class ExamAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    annotator_id: UUID
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    status: str
    score: float | None
    passed: bool | None
    answers_json: dict[str, Any]
    task_times_json: dict[str, Any]
    integrity_score: float
    review_notes: str | None
    released_at: datetime | None
    released_by: UUID | None


class ExamAnswerSave(BaseModel):
    task_id: str = Field(min_length=1, max_length=512)
    annotation_json: dict[str, Any]
    time_spent_seconds: float | None = Field(default=None, ge=0)

    @field_validator("task_id")
    @classmethod
    def strip_task_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("task_id cannot be blank")
        return s


class IntegrityEventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=128)
    severity: IntegritySeverity
    payload_json: dict[str, Any] = Field(default_factory=dict)


class IntegrityEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attempt_id: UUID
    event_type: str
    severity: str
    payload_json: dict[str, Any]
    created_at: datetime


class ExamAttemptSubmitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    status: str
    submitted_at: datetime | None
    score: float | None
    passed: bool | None
    integrity_score: float


class ExamResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_id: UUID
    exam_id: UUID
    status: str
    score: float | None
    passed: bool | None
    integrity_score: float
    submitted_at: datetime | None
    released_at: datetime | None
    review_notes: str | None
    total_gold_tasks: int | None = None
    scored_tasks: int | None = None


class ReviewAttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    exam_title: str
    annotator_id: UUID
    annotator_email: str | None = None
    started_at: datetime
    expires_at: datetime
    submitted_at: datetime | None
    status: str
    score: float | None
    passed: bool | None
    integrity_score: float
    review_notes: str | None
    released_at: datetime | None


class ReviewReleaseRequest(BaseModel):
    release: bool = True
    review_notes: str | None = Field(default=None, max_length=16_384)


class ReviewReleaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exam_id: UUID
    status: str
    released_at: datetime | None
    released_by: UUID | None
    review_notes: str | None
