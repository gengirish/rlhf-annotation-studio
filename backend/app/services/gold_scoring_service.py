from typing import Any

from app.schemas.gold_scoring import GoldScoreResponse, TaskScore


class GoldScoringService:
    """Score annotations against optional per-task `gold` labels in task JSON."""

    @staticmethod
    def _task_type(task: dict[str, Any]) -> str:
        raw = task.get("type")
        if isinstance(raw, str):
            return raw.strip().lower()
        return ""

    @staticmethod
    def _dimension_scales(task: dict[str, Any]) -> dict[str, int]:
        out: dict[str, int] = {}
        dims = task.get("dimensions")
        if not isinstance(dims, list):
            return out
        for d in dims:
            if not isinstance(d, dict):
                continue
            name = d.get("name")
            scale = d.get("scale")
            if isinstance(name, str) and name.strip() and isinstance(scale, int) and scale >= 2:
                out[str(name)] = scale
        return out

    def score_workspace(self, tasks: list[dict[str, Any]] | None, annotations: dict[str, Any]) -> GoldScoreResponse:
        task_list = tasks if isinstance(tasks, list) else []
        ann = annotations if isinstance(annotations, dict) else {}

        total_gold = 0
        scored_with_annotation = 0
        task_scores: list[TaskScore] = []
        overall_parts: list[float] = []

        for task in task_list:
            if not isinstance(task, dict):
                continue
            tid = task.get("id")
            if tid is None or not str(tid).strip():
                continue
            task_id = str(tid)
            gold = task.get("gold")
            if not isinstance(gold, dict) or not gold:
                continue

            total_gold += 1
            ann_entry = ann.get(task_id)
            if not isinstance(ann_entry, dict):
                task_scores.append(
                    TaskScore(task_id=task_id, preference_correct=None, overall_score=0.0),
                )
                overall_parts.append(0.0)
                continue

            scored_with_annotation += 1

            ttype = self._task_type(task)
            scales = self._dimension_scales(task)

            pref_correct: bool | None = None
            pref_scores: list[float] = []

            if ttype == "comparison" and "preference" in gold:
                g_pref = gold["preference"]
                a_pref = ann_entry.get("preference")
                if isinstance(g_pref, int) and isinstance(a_pref, int):
                    pref_correct = a_pref == g_pref
                    pref_scores.append(1.0 if pref_correct else 0.0)

            dim_acc: dict[str, float] = {}
            dim_scores: list[float] = []
            gold_dims = gold.get("dimensions")
            if isinstance(gold_dims, dict):
                ann_dims = ann_entry.get("dimensions")
                if isinstance(ann_dims, dict):
                    for dim_name, g_val in gold_dims.items():
                        if not isinstance(dim_name, str) or not dim_name:
                            continue
                        scale = scales.get(dim_name)
                        if scale is None:
                            continue
                        a_val = ann_dims.get(dim_name)
                        if not isinstance(g_val, int) or not isinstance(a_val, int):
                            continue
                        denom = scale - 1
                        if denom <= 0:
                            acc = 1.0 if g_val == a_val else 0.0
                        else:
                            acc = max(0.0, min(1.0, 1.0 - abs(a_val - g_val) / denom))
                        dim_acc[dim_name] = acc
                        dim_scores.append(acc)

            components: list[float] = []
            components.extend(pref_scores)
            components.extend(dim_scores)

            if components:
                overall = sum(components) / len(components)
            else:
                overall = 0.0

            task_scores.append(
                TaskScore(
                    task_id=task_id,
                    preference_correct=pref_correct,
                    dimension_accuracy=dim_acc,
                    overall_score=overall,
                )
            )
            overall_parts.append(overall)

        overall_accuracy = sum(overall_parts) / len(overall_parts) if overall_parts else 0.0

        return GoldScoreResponse(
            total_gold_tasks=total_gold,
            scored_tasks=scored_with_annotation,
            overall_accuracy=overall_accuracy,
            task_scores=task_scores,
        )
