from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator
    from app.models.work_session import WorkSession


class WorkspaceRevision(Base):
    __tablename__ = "workspace_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("work_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    annotations_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    task_times_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[WorkSession] = relationship("WorkSession", back_populates="workspace_revisions")
    annotator: Mapped[Annotator] = relationship("Annotator")
