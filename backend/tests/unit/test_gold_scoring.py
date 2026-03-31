"""Unit tests for GoldScoringService.score_workspace (pure logic)."""

from __future__ import annotations

import pytest

from app.services.gold_scoring_service import GoldScoringService


def _dim_acc(scale: int, gold: int, annotated: int) -> float:
    denom = scale - 1
    if denom <= 0:
        return 1.0 if gold == annotated else 0.0
    return max(0.0, min(1.0, 1.0 - abs(annotated - gold) / denom))


def test_no_gold_tasks() -> None:
    svc = GoldScoringService()
    tasks = [{"id": "t-1", "type": "comparison"}]
    r = svc.score_workspace(tasks, {"t-1": {"preference": 0, "status": "done"}})
    assert r.total_gold_tasks == 0
    assert r.scored_tasks == 0
    assert r.overall_accuracy == 0.0
    assert r.task_scores == []


def test_perfect_comparison_score() -> None:
    svc = GoldScoringService()
    tasks = [
        {
            "id": "t-1",
            "type": "comparison",
            "gold": {"preference": 0},
        },
    ]
    annotations = {"t-1": {"preference": 0}}
    r = svc.score_workspace(tasks, annotations)
    assert r.total_gold_tasks == 1
    assert r.scored_tasks == 1
    assert r.overall_accuracy == pytest.approx(1.0)
    assert len(r.task_scores) == 1
    assert r.task_scores[0].preference_correct is True
    assert r.task_scores[0].overall_score == pytest.approx(1.0)


def test_wrong_comparison_preference() -> None:
    svc = GoldScoringService()
    tasks = [
        {
            "id": "t-1",
            "type": "comparison",
            "gold": {"preference": 0},
        },
    ]
    annotations = {"t-1": {"preference": 1}}
    r = svc.score_workspace(tasks, annotations)
    assert r.task_scores[0].preference_correct is False
    assert r.task_scores[0].overall_score == pytest.approx(0.0)


def test_dimension_accuracy_calculation() -> None:
    svc = GoldScoringService()
    tasks = [
        {
            "id": "t-1",
            "type": "rating",
            "dimensions": [
                {"name": "Accuracy", "description": "...", "scale": 5},
                {"name": "Helpfulness", "description": "...", "scale": 5},
            ],
            "gold": {
                "dimensions": {"Accuracy": 4, "Helpfulness": 3},
            },
        },
    ]
    annotations = {
        "t-1": {
            "dimensions": {"Accuracy": 4, "Helpfulness": 3},
        },
    }
    r = svc.score_workspace(tasks, annotations)
    ts = r.task_scores[0]
    assert ts.dimension_accuracy["Accuracy"] == pytest.approx(_dim_acc(5, 4, 4))
    assert ts.dimension_accuracy["Helpfulness"] == pytest.approx(_dim_acc(5, 3, 3))
    assert ts.overall_score == pytest.approx(1.0)


def test_partial_accuracy() -> None:
    svc = GoldScoringService()
    tasks = [
        {
            "id": "t-1",
            "type": "rating",
            "dimensions": [
                {"name": "A", "description": "x", "scale": 5},
                {"name": "B", "description": "x", "scale": 5},
            ],
            "gold": {"dimensions": {"A": 1, "B": 5}},
        },
    ]
    annotations = {"t-1": {"dimensions": {"A": 1, "B": 1}}}
    r = svc.score_workspace(tasks, annotations)
    acc_a = _dim_acc(5, 1, 1)
    acc_b = _dim_acc(5, 5, 1)
    ts = r.task_scores[0]
    assert ts.dimension_accuracy["A"] == pytest.approx(acc_a)
    assert ts.dimension_accuracy["B"] == pytest.approx(acc_b)
    assert ts.overall_score == pytest.approx((acc_a + acc_b) / 2)


def test_missing_annotation_for_gold_task() -> None:
    svc = GoldScoringService()
    tasks = [
        {
            "id": "t-1",
            "type": "comparison",
            "gold": {"preference": 0},
        },
    ]
    r = svc.score_workspace(tasks, {})
    assert r.total_gold_tasks == 1
    assert r.scored_tasks == 0
    assert r.overall_accuracy == pytest.approx(0.0)
    assert r.task_scores[0].overall_score == pytest.approx(0.0)
    assert r.task_scores[0].preference_correct is None


def test_empty_workspace() -> None:
    svc = GoldScoringService()
    r = svc.score_workspace(None, None)
    assert r.total_gold_tasks == 0
    assert r.scored_tasks == 0
    assert r.overall_accuracy == 0.0
    assert r.task_scores == []

    r2 = svc.score_workspace([], {})
    assert r2.total_gold_tasks == 0
