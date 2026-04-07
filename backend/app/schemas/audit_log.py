from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    org_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    details_json: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogQuery(BaseModel):
    actor_id: uuid.UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    skip: int = 0
    limit: int = 50


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    skip: int
    limit: int


class AuditLogStatsResponse(BaseModel):
    """Counts per action string for rolling windows (used by GET /audit/stats)."""

    last_24h: dict[str, int] = Field(default_factory=dict)
    last_7d: dict[str, int] = Field(default_factory=dict)
    last_30d: dict[str, int] = Field(default_factory=dict)
