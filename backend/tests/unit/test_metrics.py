"""Unit tests for compute_session_metrics_summary (pure function)."""

from __future__ import annotations

import pytest

from app.services.metrics_service import compute_session_metrics_summary


def test_empty_session() -> None:
    s = compute_session_metrics_summary(None, None, None)
    assert s.total_tasks == 0
    assert s.completed_tasks == 0
    assert s.skipped_tasks == 0
    assert s.pending_tasks == 0
    assert s.completion_rate == 0.0
    assert s.avg_time_seconds == 0.0
    assert s.median_time_seconds == 0.0
    assert s.total_time_seconds == 0.0
    assert s.dimension_averages == {}
    assert s.tasks_by_type == {}

    s2 = compute_session_metrics_summary([], {}, {})
    assert s2.total_tasks == 0
    assert s2.pending_tasks == 0


def test_basic_metrics() -> None:
    tasks = [
        {"id": "a", "type": "comparison"},
        {"id": "b", "type": "rating"},
        {"id": "c", "type": "ranking"},
    ]
    annotations = {
        "a": {"status": "done"},
        "b": {"status": "done"},
    }
    task_times = {"a": 10.0, "b": 20.0, "c": 30.0}
    s = compute_session_metrics_summary(tasks, annotations, task_times)
    assert s.total_tasks == 3
    assert s.completed_tasks == 2
    assert s.skipped_tasks == 0
    assert s.pending_tasks == 1
    assert s.completion_rate == pytest.approx(2 / 3)


def test_skipped_tasks_counted() -> None:
    tasks = [
        {"id": "x", "type": "comparison"},
        {"id": "y", "type": "comparison"},
    ]
    annotations = {
        "x": {"status": "done"},
        "y": {"status": "skipped"},
    }
    s = compute_session_metrics_summary(tasks, annotations, {})
    assert s.completed_tasks == 1
    assert s.skipped_tasks == 1
    assert s.pending_tasks == 0


def test_dimension_averages() -> None:
    tasks = [{"id": "t1", "type": "comparison"}, {"id": "t2", "type": "comparison"}]
    annotations = {
        "t1": {"status": "done", "dimensions": {"Accuracy": 4, "Helpfulness": 2}},
        "t2": {"status": "done", "dimensions": {"Accuracy": 2, "Helpfulness": 4}},
    }
    s = compute_session_metrics_summary(tasks, annotations, {})
    assert s.dimension_averages["Accuracy"] == pytest.approx(3.0)
    assert s.dimension_averages["Helpfulness"] == pytest.approx(3.0)


def test_tasks_by_type() -> None:
    tasks = [
        {"id": "1", "type": "Comparison"},
        {"id": "2", "type": "RATING"},
        {"id": "3", "type": "ranking"},
    ]
    s = compute_session_metrics_summary(tasks, {}, {})
    assert s.tasks_by_type == {"comparison": 1, "rating": 1, "ranking": 1}


def test_time_statistics() -> None:
    tasks = [{"id": "only", "type": "x"}]
    task_times = {"only": 10, "other": 20, "third": 30}
    s = compute_session_metrics_summary(tasks, {}, task_times)
    assert s.avg_time_seconds == pytest.approx(20.0)
    assert s.median_time_seconds == pytest.approx(20.0)
    assert s.total_time_seconds == pytest.approx(60.0)


def test_ignores_boolean_times() -> None:
    tasks = [{"id": "t", "type": "x"}]
    task_times = {"a": 100, "b": True, "c": False, "d": 200}
    s = compute_session_metrics_summary(tasks, {}, task_times)
    assert s.avg_time_seconds == pytest.approx(150.0)
    assert s.total_time_seconds == pytest.approx(300.0)


def test_completion_rate_percentage() -> None:
    tasks = [
        {"id": "1", "type": "a"},
        {"id": "2", "type": "a"},
        {"id": "3", "type": "a"},
        {"id": "4", "type": "a"},
    ]
    annotations = {
        "1": {"status": "done"},
        "2": {"status": "done"},
    }
    s = compute_session_metrics_summary(tasks, annotations, {})
    assert s.completion_rate == pytest.approx(0.5)
