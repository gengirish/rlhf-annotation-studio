import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
    created_at: datetime

    model_config = {"from_attributes": True}
