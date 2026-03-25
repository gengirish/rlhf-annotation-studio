from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
