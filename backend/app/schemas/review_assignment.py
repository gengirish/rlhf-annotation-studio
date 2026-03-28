from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewAssignRequest(BaseModel):
    task_pack_id: uuid.UUID
    task_id: str = Field(min_length=1, max_length=255)
    annotator_id: uuid.UUID


class BulkAssignRequest(BaseModel):
    task_pack_id: uuid.UUID
    annotator_id: uuid.UUID


class ReviewAssignmentUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=32)
    reviewer_notes: str | None = None


class ReviewSubmitRequest(BaseModel):
    annotation_json: dict[str, Any] = Field(default_factory=dict)


class ReviewAssignmentRead(BaseModel):
    id: uuid.UUID
    task_pack_id: uuid.UUID
    task_id: str
    annotator_id: uuid.UUID
    status: str
    annotation_json: dict[str, Any] | None
    reviewer_id: uuid.UUID | None
    reviewer_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
