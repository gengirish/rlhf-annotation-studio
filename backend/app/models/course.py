from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.task_pack import TaskPack


class CourseModule(Base):
    __tablename__ = "course_modules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    overview_md: Mapped[str] = mapped_column(Text, default="")
    prerequisites: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_time: Mapped[str] = mapped_column(String(64), default="")
    skills_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    bridge_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list[CourseSession]] = relationship(
        "CourseSession",
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="CourseSession.sort_order",
    )


class CourseSession(Base):
    __tablename__ = "course_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_modules.id", ondelete="CASCADE"),
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    overview_md: Mapped[str] = mapped_column(Text, default="")
    rubric_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    exercises_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_tasks_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    resources_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[str] = mapped_column(String(64), default="90-120 minutes")
    objectives_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    outline_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    module: Mapped[CourseModule] = relationship("CourseModule", back_populates="sessions")
    task_packs: Mapped[list[TaskPack]] = relationship("TaskPack", back_populates="session")
