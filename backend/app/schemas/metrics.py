from datetime import datetime

from pydantic import BaseModel


class SessionMetricsSummary(BaseModel):
    total_tasks: int
    completed_tasks: int
    skipped_tasks: int
    pending_tasks: int
    completion_rate: float
    avg_time_seconds: float
    median_time_seconds: float
    total_time_seconds: float
    dimension_averages: dict[str, float]
    tasks_by_type: dict[str, int]


class TimelinePoint(BaseModel):
    revision_number: int
    created_at: datetime
    completed_count: int


class SessionTimeline(BaseModel):
    points: list[TimelinePoint]
