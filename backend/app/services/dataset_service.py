from __future__ import annotations

import csv
import io
import json
import math
import random
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotator import Annotator
from app.models.dataset import Dataset, DatasetVersion
from app.models.review_assignment import ReviewAssignment
from app.models.task_pack import TaskPack
from app.schemas.dataset import BulkImportRequest, DatasetCreate

STATUS_SUBMITTED = "submitted"
DELETED_TAG = "__deleted__"
TASK_TYPES = frozenset({"comparison", "rating", "ranking", "mixed"})


class DatasetService:
    """Dataset lifecycle, snapshots from task packs / review assignments, and training exports."""

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _task_type(task: dict[str, Any]) -> str:
        raw = task.get("type")
        return raw.strip().lower() if isinstance(raw, str) else ""

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

    @staticmethod
    def _response_texts(task: dict[str, Any]) -> list[str]:
        responses = task.get("responses")
        if not isinstance(responses, list):
            return []
        texts: list[str] = []
        for r in responses:
            if isinstance(r, dict) and isinstance(r.get("text"), str):
                texts.append(r["text"])
            else:
                texts.append("")
        return texts

    @staticmethod
    def _chosen_rejected_texts(task: dict[str, Any], preference: int) -> tuple[str, str] | None:
        texts = DatasetService._response_texts(task)
        if not texts:
            return None
        if preference < 0 or preference >= len(texts):
            return None
        chosen = texts[preference]
        for j, t in enumerate(texts):
            if j != preference and t.strip():
                return chosen, t
        return None

    @staticmethod
    def _normalized_dimension_score(
        task: dict[str, Any], ann_dims: dict[str, Any] | None
    ) -> float | None:
        if not isinstance(ann_dims, dict) or not ann_dims:
            return None
        scales = DatasetService._dimension_scales(task)
        parts: list[float] = []
        for name, scale in scales.items():
            raw = ann_dims.get(name)
            if not isinstance(raw, int):
                continue
            denom = scale - 1
            if denom <= 0:
                parts.append(1.0 if raw == 0 else 0.0)
            else:
                parts.append(max(0.0, min(1.0, float(raw) / denom)))
        if not parts:
            return None
        return sum(parts) / len(parts)

    @staticmethod
    def _orpo_scores(task: dict[str, Any], annotation: dict[str, Any]) -> tuple[float, float]:
        """Pair of (score_chosen, score_rejected) in [0, 1] for ORPO-style margin training."""
        raw = annotation.get("raw")
        dims = annotation.get("dimensions")
        if not isinstance(dims, dict) and isinstance(raw, dict):
            dims = raw.get("dimensions")
        if not isinstance(dims, dict):
            dims = {}
        norm = DatasetService._normalized_dimension_score(task, dims)
        if norm is None:
            return 1.0, 0.0
        margin = max(0.05, min(0.45, (norm - 0.5) * 0.8 + 0.2))
        score_chosen = max(0.0, min(1.0, 0.5 + margin))
        score_rejected = max(0.0, min(1.0, 0.5 - margin))
        return score_chosen, score_rejected

    @staticmethod
    def _canonical_annotation_payload(annotation: dict[str, Any]) -> str:
        """Stable JSON for diffing (excludes volatile timestamps if present)."""
        raw = dict(annotation)
        raw.pop("updated_at", None)
        return json.dumps(raw, sort_keys=True, default=str)

    @staticmethod
    def _parse_jsonl_tasks_payload(tasks: list[Any]) -> list[dict[str, Any]]:
        """Allow BulkImportRequest.tasks to be either list[dict] or list[str] JSON lines."""
        out: list[dict[str, Any]] = []
        for item in tasks:
            if isinstance(item, dict):
                out.append(item)
                continue
            if isinstance(item, str):
                line = item.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid JSONL task line: {exc}",
                    ) from exc
                if not isinstance(parsed, dict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Each JSONL task line must be a JSON object",
                    )
                out.append(parsed)
                continue
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tasks must be a list of objects or JSON strings",
            )
        return out

    @classmethod
    async def _build_snapshot_from_packs(
        cls, db: AsyncSession, pack_ids: list[uuid.UUID]
    ) -> dict[str, Any]:
        tasks_by_id: dict[str, dict[str, Any]] = {}
        ordered_pack_ids: list[str] = []

        for pid in pack_ids:
            pack = await db.get(TaskPack, pid)
            if pack is None:
                continue
            ordered_pack_ids.append(str(pid))
            for task in pack.tasks_json or []:
                if isinstance(task, dict) and task.get("id") is not None:
                    tid = str(task["id"]).strip()
                    if tid:
                        tasks_by_id[tid] = dict(task)

        annotations: dict[str, list[dict[str, Any]]] = {}
        if pack_ids:
            result = await db.execute(
                select(ReviewAssignment)
                .where(ReviewAssignment.task_pack_id.in_(pack_ids))
                .where(ReviewAssignment.status == STATUS_SUBMITTED)
            )
            rows = result.scalars().all()
            for ra in rows:
                tid = str(ra.task_id)
                ann = dict(ra.annotation_json) if isinstance(ra.annotation_json, dict) else {}
                entry: dict[str, Any] = {
                    "annotator_id": str(ra.annotator_id),
                    "task_pack_id": str(ra.task_pack_id),
                    "preference": ann.get("preference"),
                    "dimensions": ann.get("dimensions")
                    if isinstance(ann.get("dimensions"), dict)
                    else {},
                    "raw": ann,
                    "updated_at": ra.updated_at.isoformat() if ra.updated_at else None,
                }
                annotations.setdefault(tid, []).append(entry)

        return {
            "tasks": list(tasks_by_id.values()),
            "task_order": list(tasks_by_id.keys()),
            "source_pack_ids": ordered_pack_ids,
            "annotations": annotations,
            "built_at": cls._now_iso(),
        }

    @classmethod
    def compute_stats(cls, version: DatasetVersion) -> dict[str, Any]:
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks = [t for t in (snap.get("tasks") or []) if isinstance(t, dict)]
        annotations = snap.get("annotations") if isinstance(snap.get("annotations"), dict) else {}

        task_ids = {str(t.get("id")) for t in tasks if t.get("id") is not None}
        type_breakdown: Counter[str] = Counter()
        for t in tasks:
            tt = cls._task_type(t)
            type_breakdown[tt or "unknown"] += 1

        annotator_ids: set[str] = set()
        annotated_tasks: set[str] = set()
        preference_agreement_scores: list[float] = []

        for tid, ann_list in annotations.items():
            if not isinstance(ann_list, list):
                continue
            prefs: list[int] = []
            for a in ann_list:
                if not isinstance(a, dict):
                    continue
                aid = a.get("annotator_id")
                if isinstance(aid, str) and aid:
                    annotator_ids.add(aid)
                annotated_tasks.add(tid)
                pref = a.get("preference")
                if isinstance(pref, int):
                    prefs.append(pref)
            if len(prefs) >= 2:
                ctr = Counter(prefs)
                mode_count = ctr.most_common(1)[0][1]
                preference_agreement_scores.append(mode_count / len(prefs))

        total_tasks = len(task_ids) if task_ids else len(tasks)
        completion_rate = (len(annotated_tasks) / total_tasks) if total_tasks else 0.0
        agreement = (
            sum(preference_agreement_scores) / len(preference_agreement_scores)
            if preference_agreement_scores
            else None
        )

        return {
            "task_count": total_tasks,
            "annotator_count": len(annotator_ids),
            "type_breakdown": dict(type_breakdown),
            "annotated_task_count": len(annotated_tasks),
            "completion_rate": round(completion_rate, 6),
            "preference_agreement_mean": round(agreement, 6) if agreement is not None else None,
        }

    @classmethod
    def diff_versions(cls, v1: DatasetVersion, v2: DatasetVersion) -> dict[str, Any]:
        s1 = v1.snapshot_json if isinstance(v1.snapshot_json, dict) else {}
        s2 = v2.snapshot_json if isinstance(v2.snapshot_json, dict) else {}

        def task_map(sn: dict[str, Any]) -> dict[str, dict[str, Any]]:
            m: dict[str, dict[str, Any]] = {}
            for t in sn.get("tasks") or []:
                if isinstance(t, dict) and t.get("id") is not None:
                    m[str(t["id"])] = t
            return m

        def ann_map(sn: dict[str, Any]) -> dict[str, str]:
            am: dict[str, str] = {}
            raw = sn.get("annotations") or {}
            if not isinstance(raw, dict):
                return am
            for tid, lst in raw.items():
                if isinstance(lst, list):
                    canon = sorted(
                        (cls._canonical_annotation_payload(x) for x in lst if isinstance(x, dict)),
                    )
                    am[str(tid)] = json.dumps(canon, sort_keys=True)
                else:
                    am[str(tid)] = json.dumps(lst, sort_keys=True, default=str)
            return am

        tm1, tm2 = task_map(s1), task_map(s2)
        am1, am2 = ann_map(s1), ann_map(s2)
        ids1, ids2 = set(tm1), set(tm2)

        added_tasks = sorted(ids2 - ids1)
        removed_tasks = sorted(ids1 - ids2)
        common = ids1 & ids2
        modified_tasks = sorted(tid for tid in common if am1.get(tid) != am2.get(tid))

        return {
            "from_version": v1.version,
            "to_version": v2.version,
            "added_tasks": added_tasks,
            "removed_tasks": removed_tasks,
            "modified_tasks": modified_tasks,
        }

    @classmethod
    def _filtered_tasks_and_annotations(
        cls,
        snapshot: dict[str, Any],
        filters: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        tasks = [t for t in (snapshot.get("tasks") or []) if isinstance(t, dict)]
        annotations_raw = snapshot.get("annotations") or {}
        if not isinstance(annotations_raw, dict):
            annotations_raw = {}

        type_filter: set[str] | None = None
        annotator_filter: set[str] | None = None
        if isinstance(filters, dict):
            tf = filters.get("task_types")
            if isinstance(tf, list) and tf:
                type_filter = {str(x).strip().lower() for x in tf if str(x).strip()}
            af = filters.get("annotator_ids")
            if isinstance(af, list) and af:
                annotator_filter = {str(x) for x in af}

        tasks_out: list[dict[str, Any]] = []
        for t in tasks:
            tid = t.get("id")
            if tid is None:
                continue
            tt = cls._task_type(t)
            if type_filter is not None and tt not in type_filter:
                continue
            tasks_out.append(t)

        anns_out: dict[str, list[dict[str, Any]]] = {}
        for t in tasks_out:
            tid = str(t["id"])
            lst = annotations_raw.get(tid)
            if not isinstance(lst, list):
                continue
            kept: list[dict[str, Any]] = []
            for a in lst:
                if not isinstance(a, dict):
                    continue
                if annotator_filter is not None:
                    aid = a.get("annotator_id")
                    if str(aid) not in annotator_filter:
                        continue
                kept.append(a)
            if kept:
                anns_out[tid] = kept

        return tasks_out, anns_out

    @classmethod
    def _split_indices(
        cls, n: int, split: dict[str, float] | None, seed: int = 42
    ) -> dict[str, list[int]]:
        if not split or n == 0:
            return {"all": list(range(n))}
        rng = random.Random(seed)
        idx = list(range(n))
        rng.shuffle(idx)
        ratios = {k: float(v) for k, v in split.items() if float(v) > 0}
        total_r = sum(ratios.values())
        if total_r <= 0:
            return {"all": idx}
        norm = {k: v / total_r for k, v in ratios.items()}
        cuts: dict[str, list[int]] = {k: [] for k in norm}
        cursor = 0
        keys = list(norm.keys())
        for i, k in enumerate(keys):
            if i == len(keys) - 1:
                end = n
            else:
                end = cursor + int(math.floor(norm[k] * n))
                end = min(max(cursor, end), n)
            chosen = idx[cursor:end]
            cuts[k] = chosen
            cursor = end
        if cursor < n:
            cuts[keys[-1]].extend(idx[cursor:])
        return cuts

    @classmethod
    def export_jsonl(cls, version: DatasetVersion, filters: dict[str, Any] | None = None) -> str:
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks, annotations = cls._filtered_tasks_and_annotations(snap, filters)
        lines: list[str] = []
        for task in tasks:
            tid = str(task["id"])
            for ann in annotations.get(tid, []):
                rec = {
                    "task_id": tid,
                    "task_type": cls._task_type(task),
                    "prompt": task.get("prompt") if isinstance(task.get("prompt"), str) else "",
                    "responses": task.get("responses"),
                    "preference": ann.get("preference"),
                    "dimensions": ann.get("dimensions"),
                    "annotator": ann.get("annotator_id"),
                    "timestamp": ann.get("updated_at"),
                }
                lines.append(json.dumps(rec, ensure_ascii=False, default=str))
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def export_dpo(cls, version: DatasetVersion, filters: dict[str, Any] | None = None) -> str:
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks, annotations = cls._filtered_tasks_and_annotations(snap, filters)
        lines: list[str] = []
        for task in tasks:
            if cls._task_type(task) != "comparison":
                continue
            tid = str(task["id"])
            prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
            for ann in annotations.get(tid, []):
                pref = ann.get("preference")
                if not isinstance(pref, int):
                    continue
                pair = cls._chosen_rejected_texts(task, pref)
                if pair is None:
                    continue
                chosen, rejected = pair
                row = {"prompt": prompt, "chosen": chosen, "rejected": rejected}
                lines.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def export_orpo(cls, version: DatasetVersion, filters: dict[str, Any] | None = None) -> str:
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks, annotations = cls._filtered_tasks_and_annotations(snap, filters)
        lines: list[str] = []
        for task in tasks:
            if cls._task_type(task) != "comparison":
                continue
            tid = str(task["id"])
            prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
            for ann in annotations.get(tid, []):
                pref = ann.get("preference")
                if not isinstance(pref, int):
                    continue
                pair = cls._chosen_rejected_texts(task, pref)
                if pair is None:
                    continue
                chosen, rejected = pair
                sc, sr = cls._orpo_scores(task, ann)
                row = {
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": rejected,
                    "score_chosen": sc,
                    "score_rejected": sr,
                }
                lines.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def export_csv(cls, version: DatasetVersion, filters: dict[str, Any] | None = None) -> str:
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks, annotations = cls._filtered_tasks_and_annotations(snap, filters)
        dim_names: list[str] = []
        seen: set[str] = set()
        for task in tasks:
            scales = cls._dimension_scales(task)
            for name in scales:
                if name not in seen:
                    seen.add(name)
                    dim_names.append(name)

        fieldnames = [
            "task_id",
            "task_type",
            "prompt",
            "annotator_id",
            "preference",
            *[f"dim_{n}" for n in dim_names],
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for task in tasks:
            tid = str(task["id"])
            tt = cls._task_type(task)
            prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
            for ann in annotations.get(tid, []):
                row: dict[str, Any] = {
                    "task_id": tid,
                    "task_type": tt,
                    "prompt": prompt,
                    "annotator_id": ann.get("annotator_id"),
                    "preference": ann.get("preference"),
                }
                dims = ann.get("dimensions")
                if not isinstance(dims, dict):
                    dims = {}
                for n in dim_names:
                    key = f"dim_{n}"
                    val = dims.get(n)
                    row[key] = val if val is not None else ""
                writer.writerow(row)
        return buf.getvalue()

    @classmethod
    def export_hf_dataset(
        cls,
        version: DatasetVersion,
        filters: dict[str, Any] | None = None,
        split: dict[str, float] | None = None,
    ) -> str:
        """JSON with splits; rows are JSONL-compatible dicts."""
        snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
        tasks, annotations = cls._filtered_tasks_and_annotations(snap, filters)
        records: list[dict[str, Any]] = []
        for task in tasks:
            tid = str(task["id"])
            tt = cls._task_type(task)
            prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
            for ann in annotations.get(tid, []):
                rec: dict[str, Any] = {
                    "task_id": tid,
                    "task_type": tt,
                    "prompt": prompt,
                    "preference": ann.get("preference"),
                    "dimensions": ann.get("dimensions"),
                    "annotator_id": ann.get("annotator_id"),
                }
                if tt == "comparison":
                    pref = ann.get("preference")
                    if isinstance(pref, int):
                        pair = cls._chosen_rejected_texts(task, pref)
                        if pair:
                            rec["chosen"] = pair[0]
                            rec["rejected"] = pair[1]
                records.append(rec)

        if not split:
            return json.dumps({"splits": {"train": records}}, ensure_ascii=False, indent=2)

        buckets = cls._split_indices(len(records), split)
        splits: dict[str, list[dict[str, Any]]] = {}
        for name, indices in buckets.items():
            splits[name] = [records[i] for i in indices if 0 <= i < len(records)]
        return json.dumps({"splits": splits}, ensure_ascii=False, indent=2)

    @classmethod
    def export(
        cls,
        version: DatasetVersion,
        *,
        format_name: str,
        split: dict[str, float] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> tuple[str, int, str]:
        """Returns (payload, row_count, filename_suffix)."""
        if format_name == "jsonl":
            data = cls.export_jsonl(version, filters)
            n = sum(1 for line in data.splitlines() if line.strip())
            return data, n, f"dataset_v{version.version}.jsonl"
        if format_name == "dpo":
            data = cls.export_dpo(version, filters)
            n = sum(1 for line in data.splitlines() if line.strip())
            return data, n, f"dpo_v{version.version}.jsonl"
        if format_name == "orpo":
            data = cls.export_orpo(version, filters)
            n = sum(1 for line in data.splitlines() if line.strip())
            return data, n, f"orpo_v{version.version}.jsonl"
        if format_name == "csv":
            data = cls.export_csv(version, filters)
            snap = version.snapshot_json if isinstance(version.snapshot_json, dict) else {}
            _, anns = cls._filtered_tasks_and_annotations(snap, filters)
            n = sum(len(v) for v in anns.values())
            return data, n, f"dataset_v{version.version}.csv"
        if format_name == "hf_dataset":
            data = cls.export_hf_dataset(version, filters, split)
            parsed = json.loads(data)
            splits = parsed.get("splits") if isinstance(parsed, dict) else None
            n = 0
            if isinstance(splits, dict):
                for v in splits.values():
                    if isinstance(v, list):
                        n += len(v)
            return data, n, f"hf_dataset_v{version.version}.json"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format: {format_name}",
        )

    @classmethod
    def validate_bulk_import(cls, data: BulkImportRequest) -> BulkImportRequest:
        if data.format == "jsonl":
            tasks_list = cls._parse_jsonl_tasks_payload(data.tasks)
        else:
            tasks_list = []
            for i, t in enumerate(data.tasks):
                if not isinstance(t, dict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"tasks[{i}] must be an object",
                    )
                tasks_list.append(t)

        seen: set[str] = set()
        for i, t in enumerate(tasks_list):
            tid = t.get("id")
            if tid is None or not str(tid).strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"tasks[{i}] must include a non-empty id",
                )
            tt = t.get("type")
            if not isinstance(tt, str) or tt.strip().lower() not in TASK_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"tasks[{i}].type must be one of {sorted(TASK_TYPES)}",
                )
            sid = str(tid).strip()
            if sid in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate task id: {sid}",
                )
            seen.add(sid)

        ann = data.annotations if isinstance(data.annotations, dict) else {}
        for key in ann:
            if str(key) not in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"annotations key '{key}' has no matching task id",
                )

        return BulkImportRequest(tasks=tasks_list, annotations=ann, format=data.format)

    @classmethod
    def bulk_import(
        cls, db: AsyncSession, user: Annotator, data: BulkImportRequest
    ) -> dict[str, Any]:
        validated = cls.validate_bulk_import(data)
        annotations_out: dict[str, list[dict[str, Any]]] = {}
        raw_ann = validated.annotations
        for tid, payload in raw_ann.items():
            stid = str(tid)
            if isinstance(payload, list):
                entries = payload
            else:
                entries = [payload]
            for entry in entries:
                if not isinstance(entry, dict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"annotation for {stid} must be object or list of objects",
                    )
                ann_obj = {
                    "annotator_id": str(user.id),
                    "task_pack_id": None,
                    "preference": entry.get("preference"),
                    "dimensions": entry.get("dimensions")
                    if isinstance(entry.get("dimensions"), dict)
                    else {},
                    "raw": entry,
                    "updated_at": cls._now_iso(),
                }
                annotations_out.setdefault(stid, []).append(ann_obj)

        snapshot = {
            "tasks": list(validated.tasks),
            "task_order": [str(t["id"]) for t in validated.tasks],
            "source_pack_ids": [],
            "annotations": annotations_out,
            "built_at": cls._now_iso(),
            "import_format": validated.format,
        }
        return snapshot

    @classmethod
    async def _next_version_number(cls, db: AsyncSession, dataset_id: uuid.UUID) -> int:
        result = await db.execute(
            select(func.coalesce(func.max(DatasetVersion.version), 0)).where(
                DatasetVersion.dataset_id == dataset_id,
            )
        )
        current = int(result.scalar_one() or 0)
        return current + 1

    @classmethod
    async def _ensure_unique_name(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        name: str,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        q = select(Dataset).where(Dataset.name == name.strip())
        if org_id is not None:
            q = q.where(Dataset.org_id == org_id)
        else:
            q = q.where(Dataset.org_id.is_(None))
        result = await db.execute(q)
        row = result.scalar_one_or_none()
        if row is None:
            return
        if exclude_id is not None and row.id == exclude_id:
            return
        tags = row.tags if isinstance(row.tags, list) else []
        if DELETED_TAG in tags:
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A dataset with this name already exists for this organization",
        )

    @classmethod
    async def create_dataset(
        cls, db: AsyncSession, user: Annotator, data: DatasetCreate
    ) -> Dataset:
        if user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization to create datasets",
            )
        await cls._ensure_unique_name(db, user.org_id, data.name)

        snapshot = await cls._build_snapshot_from_packs(db, list(data.source_pack_ids))
        export_formats = ["jsonl", "dpo", "orpo", "csv", "hf_dataset"]

        ds = Dataset(
            org_id=user.org_id,
            name=data.name.strip(),
            description=data.description.strip() if isinstance(data.description, str) else None,
            task_type=data.task_type,
            tags=list(data.tags),
            created_by=user.id,
        )
        db.add(ds)
        await db.flush()

        ver = DatasetVersion(
            dataset_id=ds.id,
            version=1,
            source_pack_ids=[str(p) for p in data.source_pack_ids],
            snapshot_json=snapshot,
            stats_json={},
            export_formats=export_formats,
            created_by=user.id,
            notes="Initial version",
        )
        ver.stats_json = cls.compute_stats(ver)
        db.add(ver)
        await db.commit()
        await db.refresh(ds)
        return ds

    @classmethod
    def _infer_task_type_from_tasks(cls, tasks: list[dict[str, Any]]) -> str:
        types = {cls._task_type(t) for t in tasks}
        types.discard("")
        if len(types) == 1:
            only = types.pop()
            if only in {"comparison", "rating", "ranking"}:
                return only
        return "mixed"

    @classmethod
    async def create_dataset_from_bulk_import(
        cls, db: AsyncSession, user: Annotator, data: BulkImportRequest
    ) -> Dataset:
        snapshot = cls.bulk_import(db, user, data)
        if user.org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must belong to an organization to import datasets",
            )
        tasks = snapshot.get("tasks") or []
        if not isinstance(tasks, list) or not tasks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Import requires at least one task",
            )
        inferred = cls._infer_task_type_from_tasks([t for t in tasks if isinstance(t, dict)])
        name = f"bulk_import_{uuid.uuid4().hex[:12]}"
        await cls._ensure_unique_name(db, user.org_id, name)

        ds = Dataset(
            org_id=user.org_id,
            name=name,
            description="Created from bulk import",
            task_type=inferred,
            tags=[],
            created_by=user.id,
        )
        db.add(ds)
        await db.flush()

        ver = DatasetVersion(
            dataset_id=ds.id,
            version=1,
            source_pack_ids=[],
            snapshot_json=snapshot,
            stats_json={},
            export_formats=["jsonl", "dpo", "orpo", "csv", "hf_dataset"],
            created_by=user.id,
            notes="Bulk import",
        )
        ver.stats_json = cls.compute_stats(ver)
        db.add(ver)
        await db.commit()
        await db.refresh(ds)
        return ds

    @classmethod
    async def create_version(
        cls,
        db: AsyncSession,
        dataset_id: uuid.UUID,
        user: Annotator,
        pack_ids: list[uuid.UUID],
        notes: str | None,
    ) -> DatasetVersion:
        ds = await db.get(Dataset, dataset_id)
        if ds is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        tags = ds.tags if isinstance(ds.tags, list) else []
        if DELETED_TAG in tags:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        snapshot = await cls._build_snapshot_from_packs(db, pack_ids)
        vn = await cls._next_version_number(db, dataset_id)
        export_formats = ["jsonl", "dpo", "orpo", "csv", "hf_dataset"]
        ver = DatasetVersion(
            dataset_id=dataset_id,
            version=vn,
            source_pack_ids=[str(p) for p in pack_ids],
            snapshot_json=snapshot,
            stats_json={},
            export_formats=export_formats,
            created_by=user.id,
            notes=notes,
        )
        ver.stats_json = cls.compute_stats(ver)
        db.add(ver)
        ds.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(ver)
        return ver

    @classmethod
    async def soft_delete_dataset(cls, db: AsyncSession, dataset_id: uuid.UUID) -> None:
        ds = await db.get(Dataset, dataset_id)
        if ds is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        tags = list(ds.tags) if isinstance(ds.tags, list) else []
        if DELETED_TAG not in tags:
            tags.append(DELETED_TAG)
        ds.tags = tags
        ds.name = f"{ds.name}__{dataset_id.hex[:8]}"
        ds.updated_at = datetime.now(UTC)
        await db.commit()
