import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AnnotatorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(None, max_length=64)


class AnnotatorRead(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    role: str = "annotator"
    org_id: uuid.UUID | None = None
    is_active: bool = True
    deactivated_at: datetime | None = None
    created_at: datetime

    @field_validator("is_active", mode="before")
    @classmethod
    def coerce_is_active(cls, v: object) -> bool:
        return v if v is not None else True

    model_config = {"from_attributes": True}
