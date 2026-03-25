from typing import Any

from app.schemas.task_validation import TaskValidationIssue

TASK_TYPE_RULES: dict[str, dict[str, Any]] = {
    "comparison": {
        "required": ["id", "type", "title", "prompt", "responses", "dimensions"],
        "min_responses": 2,
        "max_responses": None,
    },
    "rating": {
        "required": ["id", "type", "title", "prompt", "responses", "dimensions"],
        "min_responses": 1,
        "max_responses": 1,
    },
    "ranking": {
        "required": ["id", "type", "title", "prompt", "responses", "dimensions"],
        "min_responses": 2,
        "max_responses": None,
    },
}


class TaskValidationService:
    @staticmethod
    def _is_non_empty_string(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _row_label(idx: int, task: Any) -> str:
        task_id = ""
        if isinstance(task, dict):
            raw_id = task.get("id")
            if raw_id is not None:
                task_id = str(raw_id).strip()
        suffix = f' (id="{task_id}")' if task_id else ""
        return f"row {idx + 1}{suffix}"

    def validate_tasks(self, tasks: list[dict[str, Any]]) -> tuple[list[TaskValidationIssue], set[int]]:
        issues: list[TaskValidationIssue] = []
        invalid_rows: set[int] = set()
        seen_ids: dict[str, int] = {}

        def mark_invalid(idx: int, task: Any, message: str) -> None:
            invalid_rows.add(idx)
            issues.append(
                TaskValidationIssue(
                    row_index=idx + 1,
                    row_label=self._row_label(idx, task),
                    message=message,
                )
            )

        for idx, task in enumerate(tasks):
            if not isinstance(task, dict):
                mark_invalid(idx, task, "task must be an object.")
                continue

            raw_type = task.get("type")
            task_type = raw_type.strip().lower() if isinstance(raw_type, str) else ""
            rules = TASK_TYPE_RULES.get(task_type)
            if not rules:
                mark_invalid(idx, task, "type must be one of comparison, rating, ranking.")
                continue

            for field_name in rules["required"]:
                if task.get(field_name) is None:
                    mark_invalid(idx, task, f'missing required field "{field_name}" for {task_type} task.')

            task_id = task.get("id")
            if not self._is_non_empty_string(task_id):
                mark_invalid(idx, task, "id must be a non-empty string.")
            else:
                task_id_str = str(task_id)
                if task_id_str in seen_ids:
                    first_idx = seen_ids[task_id_str] + 1
                    mark_invalid(idx, task, f'duplicate id "{task_id_str}" (also used in row {first_idx}).')
                else:
                    seen_ids[task_id_str] = idx

            if not self._is_non_empty_string(task.get("title")):
                mark_invalid(idx, task, "title must be a non-empty string.")
            if not self._is_non_empty_string(task.get("prompt")):
                mark_invalid(idx, task, "prompt must be a non-empty string.")

            responses = task.get("responses")
            if not isinstance(responses, list):
                mark_invalid(idx, task, "responses must be an array.")
            else:
                count = len(responses)
                min_responses = int(rules["min_responses"])
                max_responses = rules["max_responses"]
                if count < min_responses:
                    mark_invalid(
                        idx,
                        task,
                        f"{task_type} requires at least {min_responses} response(s), found {count}.",
                    )
                if max_responses is not None and count > int(max_responses):
                    mark_invalid(
                        idx,
                        task,
                        f"{task_type} requires exactly {max_responses} response(s), found {count}.",
                    )

                for r_idx, response in enumerate(responses):
                    if not isinstance(response, dict):
                        mark_invalid(idx, task, f"responses[{r_idx}] must be an object.")
                        continue
                    if not self._is_non_empty_string(response.get("label")):
                        mark_invalid(idx, task, f"responses[{r_idx}].label must be a non-empty string.")
                    if not isinstance(response.get("text"), str):
                        mark_invalid(
                            idx,
                            task,
                            f"responses[{r_idx}].text must be a string (empty string allowed).",
                        )
                    model = response.get("model")
                    if model is not None and not isinstance(model, str):
                        mark_invalid(
                            idx,
                            task,
                            f"responses[{r_idx}].model must be a string when provided.",
                        )

            dimensions = task.get("dimensions")
            if not isinstance(dimensions, list) or len(dimensions) == 0:
                mark_invalid(idx, task, "dimensions must be a non-empty array.")
            else:
                dim_names: set[str] = set()
                for d_idx, dimension in enumerate(dimensions):
                    if not isinstance(dimension, dict):
                        mark_invalid(idx, task, f"dimensions[{d_idx}] must be an object.")
                        continue
                    name = dimension.get("name")
                    if not self._is_non_empty_string(name):
                        mark_invalid(idx, task, f"dimensions[{d_idx}].name must be a non-empty string.")
                    else:
                        name_str = str(name)
                        if name_str in dim_names:
                            mark_invalid(idx, task, f'dimensions[{d_idx}].name duplicates "{name_str}".')
                        else:
                            dim_names.add(name_str)
                    if not self._is_non_empty_string(dimension.get("description")):
                        mark_invalid(
                            idx,
                            task,
                            f"dimensions[{d_idx}].description must be a non-empty string.",
                        )
                    scale = dimension.get("scale")
                    if not isinstance(scale, int) or scale < 2:
                        mark_invalid(idx, task, f"dimensions[{d_idx}].scale must be an integer >= 2.")

        return issues, invalid_rows

