from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CertificateCreate(BaseModel):
    annotator_id: UUID
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    certificate_type: str = "course_completion"
    source_id: str | None = None


class CertificateRead(BaseModel):
    id: UUID
    annotator_id: UUID
    title: str
    description: str
    certificate_type: str
    source_id: str | None
    recipient_name: str
    issued_at: datetime
    issued_by: UUID | None

    model_config = {"from_attributes": True}


class CertificatePublic(BaseModel):
    """Public-facing certificate info (no auth required)."""

    id: UUID
    title: str
    description: str
    certificate_type: str
    recipient_name: str
    issued_at: datetime

    model_config = {"from_attributes": True}
