from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    task_type: Literal["comparison", "rating", "ranking", "mixed"]
    tags: list[str] = Field(default_factory=list)
    source_pack_ids: list[uuid.UUID] = Field(default_factory=list)


class DatasetVersionCreate(BaseModel):
    source_pack_ids: list[uuid.UUID] = Field(default_factory=list)
    notes: str | None = None


class DatasetRead(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID | None
    name: str
    description: str | None
    task_type: str
    tags: list[Any]
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version_count: int = 0

    model_config = {"from_attributes": True}


class DatasetVersionRead(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    version: int
    source_pack_ids: list[Any]
    snapshot_json: dict[str, Any]
    stats_json: dict[str, Any]
    export_formats: list[Any]
    created_by: uuid.UUID
    created_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


class DatasetDetailRead(DatasetRead):
    versions: list[DatasetVersionRead] = Field(default_factory=list)


class DatasetListResponse(BaseModel):
    items: list[DatasetRead]
    total: int


class BulkImportRequest(BaseModel):
    tasks: list[dict[str, Any] | str]
    annotations: dict[str, Any]
    format: Literal["jsonl", "json"] = "json"


class ExportRequest(BaseModel):
    format: Literal["jsonl", "dpo", "orpo", "hf_dataset", "csv"] = "jsonl"
    split: dict[str, float] | None = Field(
        default=None,
        description="Optional split ratios, e.g. {'train': 0.8, 'validation': 0.1, 'test': 0.1}",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional filters: task_types, annotator_ids, min_dimensions, etc.",
    )


class ExportResponse(BaseModel):
    data: str
    format: str
    task_count: int
    filename: str
