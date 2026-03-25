from app.services.task_validation_service import TaskValidationService


def test_task_validation_accepts_valid_task() -> None:
    tasks = [
        {
            "id": "t-1",
            "type": "rating",
            "title": "Valid Task",
            "prompt": "Prompt",
            "responses": [{"label": "Response", "text": "Some text"}],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert issues == []
    assert invalid_rows == set()


def test_task_validation_flags_duplicate_id() -> None:
    base = {
        "type": "comparison",
        "title": "Task",
        "prompt": "Prompt",
        "responses": [{"label": "A", "text": "x"}, {"label": "B", "text": "y"}],
        "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
    }
    tasks = [{"id": "dup", **base}, {"id": "dup", **base}]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert len(issues) >= 1
    assert 1 in invalid_rows
    assert any("duplicate id" in issue.message for issue in issues)

