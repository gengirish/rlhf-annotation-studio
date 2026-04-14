from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JudgeConfig(BaseModel):
    model: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    prompt_template: str | None = None
    dimensions: list[str] | None = None


class JudgeTaskRequest(BaseModel):
    task_pack_id: uuid.UUID
    task_ids: list[str] | None = None
    config: JudgeConfig = Field(default_factory=JudgeConfig)


class JudgeResult(BaseModel):
    task_id: str
    preference: int | None = None
    dimensions: dict[str, int] | None = None
    reasoning: str
    confidence: float


class JudgeBatchResponse(BaseModel):
    task_pack_id: uuid.UUID
    results: list[JudgeResult]
    judge_model: str
    total_tokens: int
    total_latency_ms: int


class EvaluationRead(BaseModel):
    id: uuid.UUID
    task_pack_id: uuid.UUID
    task_id: str
    judge_model: str
    evaluation_json: dict[str, Any]
    confidence: float | None
    human_override: dict[str, Any] | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationListResponse(BaseModel):
    items: list[EvaluationRead]
    total: int
    limit: int
    offset: int


class HumanOverrideRequest(BaseModel):
    preference: int | None = None
    dimensions: dict[str, int] | None = None
    reasoning: str | None = None
