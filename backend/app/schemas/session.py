import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.annotation_validation import AnnotationIssue
from app.schemas.annotator import AnnotatorCreate, AnnotatorRead


class BootstrapRequest(BaseModel):
    """Register annotator and create a new work session in one call."""

    annotator: AnnotatorCreate


class BootstrapResponse(BaseModel):
    annotator: AnnotatorRead
    session_id: uuid.UUID


class WorkspaceUpdate(BaseModel):
    """Full workspace snapshot from the browser (matches localStorage shape)."""

    tasks: list[dict[str, Any]] | None = None
    annotations: dict[str, Any] = Field(default_factory=dict)
    task_times: dict[str, Any] = Field(default_factory=dict)
    active_pack_file: str | None = None


class WorkspaceRead(BaseModel):
    session_id: uuid.UUID
    annotator_id: uuid.UUID
    tasks: list[dict[str, Any]] | None = None
    annotations: dict[str, Any]
    task_times: dict[str, Any]
    active_pack_file: str | None
    updated_at: datetime


class WorkspacePutResponse(BaseModel):
    ok: bool
    annotation_warnings: list[AnnotationIssue]
