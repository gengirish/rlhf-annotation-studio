from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator
    from app.models.task_pack import TaskPack


class ConsensusConfig(Base):
    __tablename__ = "consensus_configs"
    __table_args__ = (UniqueConstraint("task_pack_id", name="uq_consensus_config_task_pack"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    annotators_per_task: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    agreement_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    auto_resolve: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    task_pack: Mapped[TaskPack] = relationship("TaskPack")
    creator: Mapped[Annotator] = relationship("Annotator", foreign_keys=[created_by])
    consensus_tasks: Mapped[list[ConsensusTask]] = relationship(
        "ConsensusTask",
        back_populates="config",
        cascade="all, delete-orphan",
    )


class ConsensusTask(Base):
    __tablename__ = "consensus_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consensus_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    assigned_annotators: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    annotations_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    resolved_annotation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="SET NULL"),
        nullable=True,
    )
    agreement_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    config: Mapped[ConsensusConfig] = relationship(
        "ConsensusConfig", back_populates="consensus_tasks"
    )
    task_pack: Mapped[TaskPack] = relationship("TaskPack")
    resolver: Mapped[Annotator | None] = relationship("Annotator", foreign_keys=[resolved_by])
