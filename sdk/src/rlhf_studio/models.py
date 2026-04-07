from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskItem(BaseModel):
    id: str = ""
    title: str = ""
    type: str = ""
    prompt: str | None = None
    model_config = {"extra": "allow"}


class TaskPack(BaseModel):
    id: uuid.UUID | None = None
    slug: str | None = None
    name: str = ""
    description: str = ""
    language: str = "general"
    task_count: int = 0
    created_at: datetime | None = None
    tasks_json: list[dict[str, Any]] | None = None
    model_config = {"extra": "allow"}


class Annotation(BaseModel):
    preference: int | None = None
    dimensions: dict[str, Any] = Field(default_factory=dict)
    model_config = {"extra": "allow"}


class ReviewAssignment(BaseModel):
    id: uuid.UUID
    task_pack_id: uuid.UUID
    task_id: str
    annotator_id: uuid.UUID
    status: str
    annotation_json: dict[str, Any] | None = None
    reviewer_id: uuid.UUID | None = None
    reviewer_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"extra": "allow"}


class Dataset(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    task_type: str = "mixed"
    tags: list[Any] = Field(default_factory=list)
    created_by: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version_count: int = 0
    model_config = {"extra": "allow"}


class DimensionAgreement(BaseModel):
    dimension: str
    cohens_kappa: float | None = None
    fleiss_kappa: float | None = None
    krippendorffs_alpha: float | None = None
    percentage_agreement: float = 0.0
    n_annotators: int = 0
    n_items: int = 0


class IAAResult(BaseModel):
    task_pack_id: uuid.UUID
    preference_agreement: DimensionAgreement | None = None
    dimension_agreements: list[DimensionAgreement] = Field(default_factory=list)
    overall_kappa: float | None = None
    overall_alpha: float | None = None
    n_annotators: int = 0
    n_tasks_with_overlap: int = 0
    computed_at: datetime | None = None
    model_config = {"extra": "allow"}


class QualityScore(BaseModel):
    annotator_id: uuid.UUID | str
    score: float | None = None
    rank: int | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    model_config = {"extra": "allow"}
