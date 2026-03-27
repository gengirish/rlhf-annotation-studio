from typing import Any

from app.schemas.annotation_validation import AnnotationIssue


class AnnotationValidationService:
    """Validate workspace annotations against task definitions (non-blocking warnings)."""

    @staticmethod
    def _task_type(task: dict[str, Any]) -> str:
        raw = task.get("type")
        if isinstance(raw, str):
            return raw.strip().lower()
        return ""

    @staticmethod
    def _response_count(task: dict[str, Any]) -> int:
        responses = task.get("responses")
        return len(responses) if isinstance(responses, list) else 0

    def validate(self, tasks: list[dict[str, Any]] | None, annotations: dict[str, Any]) -> list[AnnotationIssue]:
        issues: list[AnnotationIssue] = []
        task_list = tasks if isinstance(tasks, list) else []
        task_by_id: dict[str, dict[str, Any]] = {}
        for t in task_list:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            if tid is not None and str(tid).strip():
                task_by_id[str(tid)] = t

        for raw_task_id, raw_ann in annotations.items():
            task_id = str(raw_task_id)
            if not isinstance(raw_ann, dict):
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="annotation",
                        message="annotation entry must be an object",
                    )
                )
                continue

            task = task_by_id.get(task_id)
            if task is None:
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="task_id",
                        message="annotation key does not match any task id in the current task list",
                    )
                )
                continue

            ttype = self._task_type(task)
            status = raw_ann.get("status")
            status_str = status if isinstance(status, str) else ""

            self._check_dimensions(task, raw_ann, task_id, status_str, issues)
            self._check_type_specific(task, ttype, raw_ann, task_id, status_str, issues)
            if status_str == "done":
                self._check_done_required(task, ttype, raw_ann, task_id, issues)

        return issues

    def _check_dimensions(
        self,
        task: dict[str, Any],
        ann: dict[str, Any],
        task_id: str,
        status: str,
        issues: list[AnnotationIssue],
    ) -> None:
        dim_defs = task.get("dimensions")
        if not isinstance(dim_defs, list) or not dim_defs:
            return

        ann_dims = ann.get("dimensions")
        if status == "done":
            if not isinstance(ann_dims, dict):
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="dimensions",
                        message="dimensions must be an object when status is done",
                    )
                )
                return

        if ann_dims is None:
            return
        if not isinstance(ann_dims, dict):
            issues.append(
                AnnotationIssue(
                    task_id=task_id,
                    field="dimensions",
                    message="dimensions must be an object",
                )
            )
            return

        for d in dim_defs:
            if not isinstance(d, dict):
                continue
            name = d.get("name")
            scale = d.get("scale")
            if not isinstance(name, str) or not name.strip():
                continue
            if not isinstance(scale, int) or scale < 2:
                continue
            name_str = str(name)
            if status == "done" and name_str not in ann_dims:
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field=f"dimensions.{name_str}",
                        message=f'missing dimension score for "{name_str}" when status is done',
                    )
                )
                continue
            if name_str not in ann_dims:
                continue
            val = ann_dims[name_str]
            if not isinstance(val, int) or val < 1 or val > scale:
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field=f"dimensions.{name_str}",
                        message=f"score must be an integer in [1, {scale}]",
                    )
                )

    def _check_type_specific(
        self,
        task: dict[str, Any],
        ttype: str,
        ann: dict[str, Any],
        task_id: str,
        status: str,
        issues: list[AnnotationIssue],
    ) -> None:
        if ttype == "comparison":
            pref = ann.get("preference", None)
            has_pref = "preference" in ann and pref is not None
            if has_pref and not isinstance(pref, int):
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="preference",
                        message="preference must be an integer",
                    )
                )
            if status == "done" and (not has_pref or not isinstance(pref, int)):
                if not has_pref:
                    issues.append(
                        AnnotationIssue(
                            task_id=task_id,
                            field="preference",
                            message="preference is required when status is done for comparison tasks",
                        )
                    )

        if ttype == "ranking":
            n = self._response_count(task)
            ranking = ann.get("ranking")
            if ranking is not None:
                if not isinstance(ranking, list):
                    issues.append(
                        AnnotationIssue(
                            task_id=task_id,
                            field="ranking",
                            message="ranking must be a list of integers",
                        )
                    )
                else:
                    if n > 0 and len(ranking) != n:
                        issues.append(
                            AnnotationIssue(
                                task_id=task_id,
                                field="ranking",
                                message=f"ranking must have length {n} (one entry per response)",
                            )
                        )
                    bad = [x for x in ranking if not isinstance(x, int)]
                    if bad:
                        issues.append(
                            AnnotationIssue(
                                task_id=task_id,
                                field="ranking",
                                message="ranking must be a list of integers",
                            )
                        )
            elif status == "done":
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="ranking",
                        message="ranking is required when status is done for ranking tasks",
                    )
                )

    def _check_done_required(
        self,
        task: dict[str, Any],
        ttype: str,
        ann: dict[str, Any],
        task_id: str,
        issues: list[AnnotationIssue],
    ) -> None:
        just = ann.get("justification")
        if not isinstance(just, str) or len(just) < 10:
            issues.append(
                AnnotationIssue(
                    task_id=task_id,
                    field="justification",
                    message="justification must be a string with length >= 10 when status is done",
                )
            )

        if ttype == "rating":
            if "preference" in ann and ann["preference"] is not None:
                issues.append(
                    AnnotationIssue(
                        task_id=task_id,
                        field="preference",
                        message="preference should not be set for rating tasks",
                    )
                )
