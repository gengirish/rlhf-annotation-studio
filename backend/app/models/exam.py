from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator
    from app.models.task_pack import TaskPack


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    task_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    pass_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    task_pack: Mapped["TaskPack"] = relationship("TaskPack")
    creator: Mapped["Annotator | None"] = relationship("Annotator", foreign_keys=[created_by])
    attempts: Mapped[list["ExamAttempt"]] = relationship(
        "ExamAttempt",
        back_populates="exam",
        cascade="all, delete-orphan",
    )


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answers_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    task_times_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1.0")
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_rubric_scores_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    annotator: Mapped["Annotator"] = relationship("Annotator", foreign_keys=[annotator_id])
    releaser: Mapped["Annotator | None"] = relationship("Annotator", foreign_keys=[released_by])
    integrity_events: Mapped[list["IntegrityEvent"]] = relationship(
        "IntegrityEvent",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class IntegrityEvent(Base):
    __tablename__ = "exam_integrity_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="integrity_events")
