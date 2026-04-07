from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default=["read", "write"])
    expires_in_days: int | None = None


class APIKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    expires_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreated(APIKeyRead):
    key: str


class APIKeyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    scopes: list[str] | None = None
    is_active: bool | None = None
