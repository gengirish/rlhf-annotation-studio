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


def test_comparison_task_too_few_responses() -> None:
    tasks = [
        {
            "id": "c-1",
            "type": "comparison",
            "title": "Task",
            "prompt": "Prompt",
            "responses": [{"label": "A", "text": "only one"}],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("at least 2" in issue.message for issue in issues)


def test_rating_task_too_many_responses() -> None:
    tasks = [
        {
            "id": "r-1",
            "type": "rating",
            "title": "Task",
            "prompt": "Prompt",
            "responses": [
                {"label": "A", "text": "x"},
                {"label": "B", "text": "y"},
            ],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("exactly 1" in issue.message for issue in issues)


def test_ranking_task_too_few_responses() -> None:
    tasks = [
        {
            "id": "k-1",
            "type": "ranking",
            "title": "Task",
            "prompt": "Prompt",
            "responses": [{"label": "A", "text": "only one"}],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("at least 2" in issue.message for issue in issues)


def test_missing_required_fields() -> None:
    tasks = [
        {
            "id": "m-1",
            "type": "rating",
            "title": "T",
            # missing prompt
            "responses": [{"label": "A", "text": "x"}],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("prompt" in issue.message for issue in issues)


def test_invalid_task_type() -> None:
    tasks = [
        {
            "id": "x-1",
            "type": "invalid",
            "title": "T",
            "prompt": "P",
            "responses": [{"label": "A", "text": "x"}],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("comparison, rating, ranking" in issue.message for issue in issues)


def test_empty_dimensions_flagged() -> None:
    tasks = [
        {
            "id": "d-1",
            "type": "rating",
            "title": "T",
            "prompt": "P",
            "responses": [{"label": "A", "text": "x"}],
            "dimensions": [],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert 0 in invalid_rows
    assert any("non-empty array" in issue.message for issue in issues)


def test_valid_comparison_task() -> None:
    tasks = [
        {
            "id": "vc-1",
            "type": "comparison",
            "title": "Task",
            "prompt": "Prompt",
            "responses": [
                {"label": "A", "text": "x"},
                {"label": "B", "text": "y"},
            ],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert issues == []
    assert invalid_rows == set()


def test_valid_ranking_task() -> None:
    tasks = [
        {
            "id": "vr-1",
            "type": "ranking",
            "title": "Task",
            "prompt": "Prompt",
            "responses": [
                {"label": "A", "text": "a"},
                {"label": "B", "text": "b"},
                {"label": "C", "text": "c"},
            ],
            "dimensions": [{"name": "Accuracy", "description": "Quality", "scale": 5}],
        }
    ]
    issues, invalid_rows = TaskValidationService().validate_tasks(tasks)
    assert issues == []
    assert invalid_rows == set()

