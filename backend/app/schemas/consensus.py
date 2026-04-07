from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConsensusConfigCreate(BaseModel):
    task_pack_id: uuid.UUID
    annotators_per_task: int = Field(default=3, ge=2, le=10)
    agreement_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    auto_resolve: bool = False


class ConsensusConfigRead(BaseModel):
    id: uuid.UUID
    task_pack_id: uuid.UUID
    annotators_per_task: int
    agreement_threshold: float
    auto_resolve: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsensusTaskRead(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID
    task_pack_id: uuid.UUID
    task_id: str
    status: str
    assigned_annotators: list[Any]
    annotations_json: dict[str, Any]
    resolved_annotation: dict[str, Any] | None
    resolved_by: uuid.UUID | None
    agreement_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsensusTaskSubmit(BaseModel):
    annotation: dict[str, Any]


class ConsensusResolveRequest(BaseModel):
    resolved_annotation: dict[str, Any]
    reasoning: str | None = None


class ConsensusStatusResponse(BaseModel):
    task_pack_id: uuid.UUID
    total_tasks: int
    agreed: int
    disputed: int
    pending: int
    in_progress: int
    resolved: int
    overall_agreement: float | None


class AnnotatorNextTaskResponse(BaseModel):
    consensus_task_id: uuid.UUID
    task_id: str
    task_data: dict[str, Any]
    annotators_completed: int
    annotators_required: int
