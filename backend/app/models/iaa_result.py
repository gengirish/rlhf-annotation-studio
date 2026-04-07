from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.task_pack import TaskPack


class IAAResult(Base):
    __tablename__ = "iaa_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_packs.id", ondelete="CASCADE"),
        index=True,
    )
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    n_annotators: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_kappa: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_alpha: Mapped[float | None] = mapped_column(Float, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task_pack: Mapped[TaskPack] = relationship("TaskPack")
