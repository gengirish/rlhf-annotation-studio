from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.dataset import BulkImportRequest
from app.services.dataset_service import DatasetService


def _version(snapshot: dict, version: int = 1) -> SimpleNamespace:
    return SimpleNamespace(snapshot_json=snapshot, version=version)


def test_export_dpo_format_correctness() -> None:
    task = {
        "id": "t1",
        "type": "comparison",
        "prompt": "Hello",
        "responses": [
            {"label": "A", "text": "chosen text"},
            {"label": "B", "text": "rejected text"},
        ],
    }
    snap = {
        "tasks": [task],
        "annotations": {
            "t1": [
                {
                    "annotator_id": str(uuid4()),
                    "task_pack_id": str(uuid4()),
                    "preference": 0,
                    "dimensions": {},
                    "raw": {"preference": 0},
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        },
    }
    out = DatasetService.export_dpo(_version(snap))
    line = out.strip().splitlines()[0]
    row = json.loads(line)
    assert row == {"prompt": "Hello", "chosen": "chosen text", "rejected": "rejected text"}


def test_export_orpo_includes_scores() -> None:
    task = {
        "id": "t1",
        "type": "comparison",
        "prompt": "P",
        "responses": [
            {"text": "c"},
            {"text": "r"},
        ],
        "dimensions": [{"name": "quality", "scale": 5}],
    }
    snap = {
        "tasks": [task],
        "annotations": {
            "t1": [
                {
                    "annotator_id": str(uuid4()),
                    "preference": 0,
                    "dimensions": {"quality": 4},
                    "raw": {},
                    "updated_at": None,
                }
            ],
        },
    }
    out = DatasetService.export_orpo(_version(snap))
    row = json.loads(out.strip().splitlines()[0])
    assert row["prompt"] == "P"
    assert row["chosen"] == "c"
    assert row["rejected"] == "r"
    assert "score_chosen" in row and "score_rejected" in row
    assert 0.0 <= row["score_chosen"] <= 1.0
    assert 0.0 <= row["score_rejected"] <= 1.0
    assert row["score_chosen"] > row["score_rejected"]


def test_jsonl_export_import_round_trip() -> None:
    task = {
        "id": "rt-1",
        "type": "comparison",
        "prompt": "Round trip prompt",
        "responses": [{"text": "A"}, {"text": "B"}],
    }
    ann = {
        "annotator_id": str(uuid4()),
        "preference": 1,
        "dimensions": {"d1": 3},
        "raw": {"preference": 1, "dimensions": {"d1": 3}},
        "updated_at": "2026-04-04T12:00:00+00:00",
    }
    snap = {"tasks": [task], "annotations": {"rt-1": [ann]}}
    jsonl = DatasetService.export_jsonl(_version(snap))
    tasks_out: dict[str, dict] = {}
    annotations_out: dict[str, dict] = {}
    for line in jsonl.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        tid = rec["task_id"]
        if tid not in tasks_out:
            tasks_out[tid] = {
                "id": tid,
                "type": rec["task_type"],
                "prompt": rec["prompt"],
                "responses": rec["responses"],
            }
        annotations_out[tid] = {
            "preference": rec["preference"],
            "dimensions": rec["dimensions"],
        }
    body = BulkImportRequest(
        tasks=list(tasks_out.values()),
        annotations=annotations_out,
        format="json",
    )
    imported = DatasetService.bulk_import(
        db=None,  # type: ignore[arg-type]
        user=SimpleNamespace(id=uuid4()),
        data=body,
    )
    assert len(imported["tasks"]) == 1
    assert imported["annotations"]["rt-1"][0]["preference"] == 1
    assert imported["annotations"]["rt-1"][0]["dimensions"] == {"d1": 3}


def test_version_diffing() -> None:
    v1 = _version(
        {
            "tasks": [{"id": "a", "type": "comparison"}, {"id": "b", "type": "comparison"}],
            "annotations": {
                "a": [{"annotator_id": "u1", "preference": 0, "dimensions": {}, "raw": {}, "updated_at": None}],
                "b": [{"annotator_id": "u1", "preference": 0, "dimensions": {}, "raw": {}, "updated_at": None}],
            },
        },
        version=1,
    )
    v2 = _version(
        {
            "tasks": [{"id": "b", "type": "comparison"}, {"id": "c", "type": "comparison"}],
            "annotations": {
                "b": [{"annotator_id": "u1", "preference": 1, "dimensions": {}, "raw": {}, "updated_at": None}],
                "c": [],
            },
        },
        version=2,
    )
    diff = DatasetService.diff_versions(v1, v2)  # type: ignore[arg-type]
    assert diff["from_version"] == 1
    assert diff["to_version"] == 2
    assert "c" in diff["added_tasks"]
    assert "a" in diff["removed_tasks"]
    assert "b" in diff["modified_tasks"]


def test_stats_computation() -> None:
    snap = {
        "tasks": [
            {"id": "x", "type": "comparison"},
            {"id": "y", "type": "rating"},
        ],
        "annotations": {
            "x": [
                {
                    "annotator_id": "ann1",
                    "preference": 0,
                    "dimensions": {},
                    "raw": {},
                    "updated_at": None,
                },
                {
                    "annotator_id": "ann2",
                    "preference": 0,
                    "dimensions": {},
                    "raw": {},
                    "updated_at": None,
                },
            ],
        },
    }
    ver = _version(snap)
    stats = DatasetService.compute_stats(ver)  # type: ignore[arg-type]
    assert stats["task_count"] == 2
    assert stats["annotator_count"] == 2
    assert stats["annotated_task_count"] == 1
    assert stats["type_breakdown"]["comparison"] == 1
    assert stats["type_breakdown"]["rating"] == 1
    assert stats["completion_rate"] == 0.5
    assert stats["preference_agreement_mean"] == 1.0


def test_bulk_import_validation_duplicate_task_id() -> None:
    body = BulkImportRequest(
        tasks=[
            {"id": "dup", "type": "comparison"},
            {"id": "dup", "type": "comparison"},
        ],
        annotations={},
        format="json",
    )
    with pytest.raises(HTTPException) as exc:
        DatasetService.validate_bulk_import(body)
    assert exc.value.status_code == 400


def test_bulk_import_validation_unknown_annotation_key() -> None:
    body = BulkImportRequest(
        tasks=[{"id": "only", "type": "rating"}],
        annotations={"missing": {}},
        format="json",
    )
    with pytest.raises(HTTPException) as exc:
        DatasetService.validate_bulk_import(body)
    assert exc.value.status_code == 400


def test_bulk_import_jsonl_string_lines() -> None:
    line = json.dumps({"id": "j1", "type": "ranking", "prompt": "p"})
    body = BulkImportRequest(tasks=[line], annotations={}, format="jsonl")
    validated = DatasetService.validate_bulk_import(body)
    assert len(validated.tasks) == 1
    assert validated.tasks[0]["id"] == "j1"
