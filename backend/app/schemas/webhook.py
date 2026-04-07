from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

VALID_WEBHOOK_EVENTS = frozenset(
    {
        "annotation.submitted",
        "annotation.updated",
        "review.assigned",
        "review.submitted",
        "review.approved",
        "review.rejected",
        "dataset.created",
        "dataset.exported",
        "task_pack.created",
        "test.ping",
    }
)


class WebhookCreate(BaseModel):
    url: str = Field(max_length=2048)
    events: list[str]
    is_active: bool = True

    @field_validator("events")
    @classmethod
    def events_must_be_valid(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one event is required")
        for e in v:
            if e not in VALID_WEBHOOK_EVENTS:
                raise ValueError(f"Invalid webhook event: {e}")
        return v


class WebhookRead(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    failure_count: int
    last_triggered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryRead(BaseModel):
    id: uuid.UUID
    endpoint_id: uuid.UUID
    event: str
    payload_json: dict[str, Any]
    response_status: int | None
    success: bool
    duration_ms: int | None
    attempts: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookTest(BaseModel):
    event: str = "test.ping"

    @field_validator("event")
    @classmethod
    def event_must_be_valid(cls, v: str) -> str:
        if v not in VALID_WEBHOOK_EVENTS:
            raise ValueError(f"Invalid webhook event: {v}")
        return v


class WebhookUpdate(BaseModel):
    url: str | None = Field(None, max_length=2048)
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("events")
    @classmethod
    def events_must_be_valid_when_set(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if not v:
            raise ValueError("At least one event is required when updating events")
        for e in v:
            if e not in VALID_WEBHOOK_EVENTS:
                raise ValueError(f"Invalid webhook event: {e}")
        return v
