from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)


class OrgRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan_tier: str
    stripe_customer_id: str | None
    max_seats: int
    max_packs: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrgUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    plan_tier: str | None = Field(None, max_length=32)
    max_seats: int | None = Field(None, ge=1)
    max_packs: int | None = Field(None, ge=0)


class OrgMemberAdd(BaseModel):
    email: EmailStr
