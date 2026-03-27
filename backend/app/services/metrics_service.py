from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkSession, WorkspaceRevision
from app.schemas.metrics import SessionMetricsSummary, SessionTimeline, TimelinePoint


def _numeric_task_times(task_times: dict[str, Any]) -> list[float]:
    out: list[float] = []
    for _k, v in task_times.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, int | float):
            out.append(float(v))
    return out


def _count_done_in_snapshot(annotations: dict[str, Any] | None) -> int:
    if not isinstance(annotations, dict):
        return 0
    n = 0
    for raw in annotations.values():
        if isinstance(raw, dict) and raw.get("status") == "done":
            n += 1
    return n


def compute_session_metrics_summary(
    tasks: list[dict[str, Any]] | None,
    annotations: dict[str, Any],
    task_times: dict[str, Any],
) -> SessionMetricsSummary:
    task_list = tasks if isinstance(tasks, list) else []
    total_tasks = len(task_list)

    tasks_by_type: dict[str, int] = defaultdict(int)
    task_ids: set[str] = set()
    for t in task_list:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if tid is not None and str(tid).strip():
            task_ids.add(str(tid))
        raw_type = t.get("type")
        ttype = raw_type.strip().lower() if isinstance(raw_type, str) else "unknown"
        tasks_by_type[ttype] += 1

    ann = annotations if isinstance(annotations, dict) else {}
    completed_tasks = 0
    skipped_tasks = 0
    dim_sum: dict[str, float] = defaultdict(float)
    dim_count: dict[str, int] = defaultdict(int)

    for task_id in task_ids:
        raw_ann = ann.get(task_id)
        if not isinstance(raw_ann, dict):
            continue
        st = raw_ann.get("status")
        status_str = st if isinstance(st, str) else ""
        if status_str == "done":
            completed_tasks += 1
            dims = raw_ann.get("dimensions")
            if isinstance(dims, dict):
                for name, val in dims.items():
                    if isinstance(name, str) and name.strip():
                        if isinstance(val, bool):
                            continue
                        if isinstance(val, int | float):
                            key = str(name)
                            dim_sum[key] += float(val)
                            dim_count[key] += 1
        elif status_str == "skipped":
            skipped_tasks += 1

    pending_tasks = max(0, total_tasks - completed_tasks - skipped_tasks)
    completion_rate = (completed_tasks / total_tasks) if total_tasks else 0.0

    tt = task_times if isinstance(task_times, dict) else {}
    times = _numeric_task_times(tt)
    if times:
        avg_time = float(statistics.mean(times))
        median_time = float(statistics.median(times))
        total_time = float(sum(times))
    else:
        avg_time = 0.0
        median_time = 0.0
        total_time = 0.0

    dimension_averages = {
        k: dim_sum[k] / dim_count[k] for k in dim_sum if dim_count[k] > 0
    }

    return SessionMetricsSummary(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        skipped_tasks=skipped_tasks,
        pending_tasks=pending_tasks,
        completion_rate=completion_rate,
        avg_time_seconds=avg_time,
        median_time_seconds=median_time,
        total_time_seconds=total_time,
        dimension_averages=dict(sorted(dimension_averages.items())),
        tasks_by_type=dict(sorted(tasks_by_type.items())),
    )


class MetricsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_session_summary(self, session_id: UUID, user_id: UUID) -> SessionMetricsSummary:
        row = await self.db.get(WorkSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if row.annotator_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

        return compute_session_metrics_summary(
            row.tasks_json,
            row.annotations_json or {},
            row.task_times_json or {},
        )

    async def get_session_timeline(self, session_id: UUID, user_id: UUID) -> SessionTimeline:
        row = await self.db.get(WorkSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if row.annotator_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

        result = await self.db.execute(
            select(WorkspaceRevision)
            .where(WorkspaceRevision.session_id == session_id)
            .order_by(WorkspaceRevision.revision_number.asc())
        )
        revisions = list(result.scalars().all())
        points = [
            TimelinePoint(
                revision_number=r.revision_number,
                created_at=r.created_at,
                completed_count=_count_done_in_snapshot(r.annotations_snapshot),
            )
            for r in revisions
        ]
        return SessionTimeline(points=points)
