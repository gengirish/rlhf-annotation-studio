from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.annotator import Annotator


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    annotator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    certificate_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="course_completion"
    )
    source_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="ID of the exam attempt or course that triggered issuance"
    )
    recipient_name: Mapped[str] = mapped_column(String(512), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("annotators.id", ondelete="SET NULL"),
        nullable=True,
    )

    annotator: Mapped["Annotator"] = relationship("Annotator", foreign_keys=[annotator_id])
    issuer: Mapped["Annotator | None"] = relationship("Annotator", foreign_keys=[issued_by])
