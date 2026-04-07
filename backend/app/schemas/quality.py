from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class QualityScoreRead(BaseModel):
    id: uuid.UUID
    annotator_id: uuid.UUID
    task_pack_id: uuid.UUID | None
    gold_accuracy: float | None
    agreement_with_experts: float | None
    agreement_with_peers: float | None
    consistency_score: float | None
    speed_percentile: float | None
    overall_trust_score: float | None
    tasks_completed: int
    calibration_passed: bool | None
    computed_at: datetime

    model_config = {"from_attributes": True}


class AnnotatorQualityEntry(BaseModel):
    annotator_id: uuid.UUID
    annotator_name: str
    overall_trust_score: float | None
    tasks_completed: int
    gold_accuracy: float | None
    rank: int


class QualityLeaderboard(BaseModel):
    annotators: list[AnnotatorQualityEntry]
    computed_at: datetime


class CalibrationTestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    task_pack_id: uuid.UUID
    passing_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    is_required: bool = True


class CalibrationTestRead(BaseModel):
    id: uuid.UUID
    name: str
    task_pack_id: uuid.UUID
    passing_threshold: float
    is_required: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CalibrationAttemptRead(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    annotator_id: uuid.UUID
    score: float
    passed: bool
    attempted_at: datetime

    model_config = {"from_attributes": True}


class CalibrationAttemptResult(BaseModel):
    passed: bool
    attempt: CalibrationAttemptRead


class CalibrationAttemptSubmit(BaseModel):
    annotations: dict[str, Any] = Field(default_factory=dict)


class QualityDriftAlert(BaseModel):
    annotator_id: uuid.UUID
    annotator_name: str
    metric: str
    previous_value: float
    current_value: float
    drift_magnitude: float
    alert_level: str


class QualityDashboard(BaseModel):
    leaderboard: QualityLeaderboard
    drift_alerts: list[QualityDriftAlert]
    org_average_trust: float
    total_annotators: int
    calibration_pass_rate: float | None
