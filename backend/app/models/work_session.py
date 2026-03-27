from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator
    from app.models.workspace_revision import WorkspaceRevision


class WorkSession(Base):
    """Server-side workspace mirror: tasks, annotations, and timing from the annotation UI."""

    __tablename__ = "work_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
        index=True,
    )
    tasks_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    annotations_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    task_times_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active_pack_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    annotator: Mapped[Annotator] = relationship("Annotator", back_populates="sessions")
    workspace_revisions: Mapped[list[WorkspaceRevision]] = relationship(
        "WorkspaceRevision",
        back_populates="session",
        cascade="all, delete-orphan",
    )
