from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class IAARequest(BaseModel):
    task_pack_id: uuid.UUID
    task_ids: list[str] | None = None


class DimensionAgreement(BaseModel):
    dimension: str
    cohens_kappa: float | None = None
    fleiss_kappa: float | None = None
    krippendorffs_alpha: float | None = None
    percentage_agreement: float = Field(ge=0.0, le=1.0)
    n_annotators: int = Field(ge=0)
    n_items: int = Field(ge=0)


class IAAResponse(BaseModel):
    task_pack_id: uuid.UUID
    preference_agreement: DimensionAgreement | None = None
    dimension_agreements: list[DimensionAgreement]
    overall_kappa: float | None = None
    overall_alpha: float | None = None
    n_annotators: int = Field(ge=0)
    n_tasks_with_overlap: int = Field(ge=0)
    computed_at: datetime
