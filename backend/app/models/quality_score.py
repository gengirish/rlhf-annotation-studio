from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator
    from app.models.organization import Organization
    from app.models.task_pack import TaskPack


class AnnotatorQualityScore(Base):
    __tablename__ = "annotator_quality_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
        index=True,
    )
    task_pack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    gold_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    agreement_with_experts: Mapped[float | None] = mapped_column(Float, nullable=True)
    agreement_with_peers: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed_percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    calibration_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    annotator: Mapped[Annotator] = relationship("Annotator", foreign_keys=[annotator_id])
    task_pack: Mapped[TaskPack | None] = relationship("TaskPack", foreign_keys=[task_pack_id])


class CalibrationTest(Base):
    __tablename__ = "calibration_tests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="CASCADE"),
        nullable=False,
    )
    passing_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, server_default="0.7"
    )
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="SET NULL"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization | None] = relationship("Organization", foreign_keys=[org_id])
    task_pack: Mapped[TaskPack] = relationship("TaskPack", foreign_keys=[task_pack_id])
    creator: Mapped[Annotator] = relationship("Annotator", foreign_keys=[created_by])


class CalibrationAttempt(Base):
    __tablename__ = "calibration_attempts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_tests.id", ondelete="CASCADE"),
        index=True,
    )
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    test: Mapped[CalibrationTest] = relationship("CalibrationTest", foreign_keys=[test_id])
    annotator: Mapped[Annotator] = relationship("Annotator", foreign_keys=[annotator_id])
