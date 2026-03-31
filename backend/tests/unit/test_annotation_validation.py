"""Unit tests for AnnotationValidationService.validate (pure logic)."""

from __future__ import annotations

from app.services.annotation_validation_service import AnnotationValidationService


def _issues(svc: AnnotationValidationService, tasks: list, annotations: dict) -> list[tuple[str, str, str]]:
    return [(i.task_id, i.field, i.message) for i in svc.validate(tasks, annotations)]


def test_valid_done_comparison() -> None:
    svc = AnnotationValidationService()
    tasks = [{"id": "c1", "type": "comparison"}]
    annotations = {
        "c1": {
            "status": "done",
            "preference": 0,
            "justification": "This is long enough.",
        },
    }
    assert svc.validate(tasks, annotations) == []


def test_missing_justification_when_done() -> None:
    svc = AnnotationValidationService()
    tasks = [{"id": "c1", "type": "comparison"}]
    annotations = {
        "c1": {
            "status": "done",
            "preference": 0,
            "justification": "short",
        },
    }
    issues = _issues(svc, tasks, annotations)
    assert any(i[1] == "justification" for i in issues)

    annotations2 = {
        "c1": {"status": "done", "preference": 0},
    }
    issues2 = _issues(svc, tasks, annotations2)
    assert any(i[1] == "justification" for i in issues2)


def test_missing_preference_for_comparison() -> None:
    svc = AnnotationValidationService()
    tasks = [{"id": "c1", "type": "comparison"}]
    annotations = {
        "c1": {
            "status": "done",
            "justification": "Ten chars!!",
        },
    }
    issues = _issues(svc, tasks, annotations)
    assert any(
        i[1] == "preference" and "required" in i[2].lower() for i in issues
    )


def test_missing_ranking_for_ranking_task() -> None:
    svc = AnnotationValidationService()
    tasks = [
        {
            "id": "r1",
            "type": "ranking",
            "responses": [{"id": "a"}, {"id": "b"}],
        },
    ]
    annotations = {
        "r1": {
            "status": "done",
            "justification": "1234567890",
        },
    }
    issues = _issues(svc, tasks, annotations)
    assert any(i[1] == "ranking" and "required" in i[2].lower() for i in issues)


def test_dimension_score_out_of_range() -> None:
    svc = AnnotationValidationService()
    tasks = [
        {
            "id": "d1",
            "type": "rating",
            "dimensions": [{"name": "Quality", "description": "x", "scale": 5}],
        },
    ]
    for val, expect_issue in [(0, True), (6, True), (3, False)]:
        annotations = {
            "d1": {
                "status": "pending",
                "dimensions": {"Quality": val},
            },
        }
        issues = _issues(svc, tasks, annotations)
        has_range = any("integer in [1" in i[2] for i in issues)
        assert has_range == expect_issue


def test_missing_dimension_when_done() -> None:
    svc = AnnotationValidationService()
    tasks = [
        {
            "id": "d1",
            "type": "rating",
            "dimensions": [{"name": "Quality", "description": "x", "scale": 5}],
        },
    ]
    annotations = {
        "d1": {
            "status": "done",
            "dimensions": {},
            "justification": "1234567890",
        },
    }
    issues = _issues(svc, tasks, annotations)
    assert any(i[1] == "dimensions.Quality" for i in issues)
    assert any("missing dimension" in i[2].lower() for i in issues)


def test_annotation_for_nonexistent_task() -> None:
    svc = AnnotationValidationService()
    tasks = [{"id": "real", "type": "comparison"}]
    annotations = {"ghost": {"status": "pending"}}
    issues = _issues(svc, tasks, annotations)
    assert any(i[0] == "ghost" and i[1] == "task_id" for i in issues)


def test_preference_on_rating_task_warned() -> None:
    svc = AnnotationValidationService()
    tasks = [{"id": "r1", "type": "rating"}]
    annotations = {
        "r1": {
            "status": "done",
            "preference": 1,
            "justification": "1234567890",
        },
    }
    issues = _issues(svc, tasks, annotations)
    assert any("preference" in i[1] and "rating" in i[2].lower() for i in issues)


def test_valid_pending_annotation() -> None:
    svc = AnnotationValidationService()
    tasks = [
        {
            "id": "c1",
            "type": "comparison",
            "dimensions": [{"name": "X", "description": "d", "scale": 3}],
        },
    ]
    annotations = {"c1": {"status": "pending"}}
    assert svc.validate(tasks, annotations) == []
