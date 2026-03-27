from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskPackCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    language: str = Field(default="general", max_length=64)
    tasks_json: list[dict[str, Any]]


class TaskPackUpdate(BaseModel):
    slug: str | None = Field(None, min_length=1, max_length=255)
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    language: str | None = Field(None, max_length=64)
    tasks_json: list[dict[str, Any]] | None = None


class TaskPackSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    language: str
    task_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskPackDetail(TaskPackSummary):
    tasks_json: list[dict[str, Any]]


class TaskPackListResponse(BaseModel):
    packs: list[TaskPackSummary]
