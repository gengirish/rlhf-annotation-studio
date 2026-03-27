from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.review_assignment import ReviewAssignment
    from app.models.work_session import WorkSession


class Annotator(Base):
    __tablename__ = "annotators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list[WorkSession]] = relationship(
        "WorkSession",
        back_populates="annotator",
        cascade="all, delete-orphan",
    )
    review_assignments: Mapped[list[ReviewAssignment]] = relationship(
        "ReviewAssignment",
        foreign_keys="ReviewAssignment.annotator_id",
        back_populates="annotator",
    )
    reviews_authored: Mapped[list[ReviewAssignment]] = relationship(
        "ReviewAssignment",
        foreign_keys="ReviewAssignment.reviewer_id",
        back_populates="reviewer",
    )
