from __future__ import annotations

import uuid
from collections import Counter
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.annotator import Annotator
from app.models.consensus import ConsensusConfig, ConsensusTask
from app.models.task_pack import TaskPack
from app.schemas.consensus import (
    AnnotatorNextTaskResponse,
    ConsensusConfigCreate,
    ConsensusStatusResponse,
    ConsensusTaskRead,
)


def pick_round_robin_assignees(
    member_ids: list[uuid.UUID], task_index: int, count: int
) -> list[uuid.UUID]:
    """Assign up to `count` unique annotators in round-robin order (fewer if org is smaller)."""
    if not member_ids or count <= 0:
        return []
    n = len(member_ids)
    k = min(count, n)
    return [member_ids[(task_index + j) % n] for j in range(k)]


def _spearman_rho_paired(r1: list[int], r2: list[int]) -> float:
    """Spearman correlation for paired ranks (same item index in both vectors)."""
    n = len(r1)
    if n != len(r2) or n < 2:
        return 1.0
    d2 = sum((int(r1[i]) - int(r2[i])) ** 2 for i in range(n))
    denom = n * (n * n - 1)
    if denom == 0:
        return 1.0
    return 1.0 - (6.0 * d2) / denom


def _ranking_list_agreement(anns: list[dict[str, Any]]) -> float:
    ranks: list[list[int]] = []
    for a in anns:
        r = a.get("ranking")
        if isinstance(r, list) and r and all(isinstance(x, int) for x in r):
            ranks.append(list(r))
    m = len(ranks)
    if m < 2:
        return 1.0 if m == 1 else 0.0
    rhos: list[float] = []
    for i in range(m):
        for j in range(i + 1, m):
            rho = _spearman_rho_paired(ranks[i], ranks[j])
            rhos.append((rho + 1.0) / 2.0)
    return sum(rhos) / len(rhos)


def compute_task_agreement(consensus_task: ConsensusTask, task_dict: dict[str, Any]) -> float:
    raw = consensus_task.annotations_json or {}
    anns = [raw[k] for k in sorted(raw.keys()) if isinstance(raw[k], dict)]
    if not anns:
        return 0.0

    ttype = task_dict.get("type") or "comparison"
    if not isinstance(ttype, str):
        ttype = "comparison"

    if ttype == "comparison":
        prefs: list[int] = []
        for a in anns:
            p = a.get("preference")
            if isinstance(p, bool):
                continue
            if isinstance(p, int):
                prefs.append(p)
            elif isinstance(p, float) and p.is_integer():
                prefs.append(int(p))
        if not prefs:
            return 0.0
        cnt = Counter(prefs)
        majority = max(cnt.values())
        return float(majority) / float(len(prefs))

    dim_scores: list[float] = []
    dims = task_dict.get("dimensions")
    if isinstance(dims, list):
        for spec in dims:
            if not isinstance(spec, dict):
                continue
            name = spec.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            scale_raw = spec.get("scale", 5)
            try:
                sc = int(scale_raw)
            except (TypeError, ValueError):
                sc = 5
            sc = max(sc, 2)
            vals: list[float] = []
            for a in anns:
                dmap = a.get("dimensions")
                if not isinstance(dmap, dict):
                    continue
                v = dmap.get(name)
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            if len(vals) < 2:
                if len(vals) == 1:
                    dim_scores.append(1.0)
                continue
            mean_v = sum(vals) / len(vals)
            mad = sum(abs(v - mean_v) for v in vals) / len(vals)
            denom = float(sc - 1)
            dim_scores.append(max(0.0, min(1.0, 1.0 - mad / denom)))

    if dim_scores:
        return sum(dim_scores) / len(dim_scores)

    if ttype == "ranking":
        return _ranking_list_agreement(anns)

    return 0.0


def _median_numeric(vals: list[float]) -> float:
    return float(median(vals))


def _mode_preference(prefs: list[int]) -> int:
    cnt = Counter(prefs)
    max_c = max(cnt.values())
    winners = sorted(k for k, v in cnt.items() if v == max_c)
    return winners[0]


def build_auto_resolved_annotation(
    annotations: list[dict[str, Any]],
    task_dict: dict[str, Any],
) -> dict[str, Any]:
    """Majority / median merge for auto_resolve."""
    if not annotations:
        return {}
    ttype = task_dict.get("type") or "comparison"
    if not isinstance(ttype, str):
        ttype = "comparison"

    out: dict[str, Any] = {"status": "done"}

    if ttype == "comparison":
        prefs: list[int] = []
        for a in annotations:
            p = a.get("preference")
            if isinstance(p, int):
                prefs.append(p)
            elif isinstance(p, float) and p.is_integer():
                prefs.append(int(p))
        if prefs:
            mp = _mode_preference(prefs)
            out["preference"] = mp
            for a in annotations:
                ap = a.get("preference")
                ai = int(ap) if isinstance(ap, (int, float)) and float(ap).is_integer() else None
                if ai == mp:
                    j = a.get("justification")
                    if isinstance(j, str) and j.strip():
                        out["justification"] = j
                        break
            if "justification" not in out:
                for a in annotations:
                    j = a.get("justification")
                    if isinstance(j, str) and j.strip():
                        out["justification"] = j
                        break

    dims = task_dict.get("dimensions")
    dim_names: list[str] = []
    if isinstance(dims, list):
        for spec in dims:
            if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                dim_names.append(spec["name"])

    merged_dim: dict[str, int] = {}
    for dname in dim_names:
        vals: list[float] = []
        for a in annotations:
            dmap = a.get("dimensions")
            if not isinstance(dmap, dict):
                continue
            v = dmap.get(dname)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                vals.append(float(v))
        if vals:
            merged_dim[dname] = int(round(_median_numeric(vals)))
    if merged_dim:
        out["dimensions"] = merged_dim

    if ttype == "ranking":
        rank_lists: list[list[int]] = []
        for a in annotations:
            r = a.get("ranking")
            if isinstance(r, list) and r and all(isinstance(x, int) for x in r):
                rank_lists.append(list(r))
        if rank_lists:
            width = len(rank_lists[0])
            if all(len(x) == width for x in rank_lists):
                merged_r: list[int] = []
                for idx in range(width):
                    col = [row[idx] for row in rank_lists]
                    merged_r.append(int(round(_median_numeric([float(x) for x in col]))))
                out["ranking"] = merged_r

    if "justification" not in out:
        for a in annotations:
            j = a.get("justification")
            if isinstance(j, str) and j.strip():
                out["justification"] = j
                break
    if "justification" not in out:
        out["justification"] = "Consensus auto-resolve."

    return out


async def _org_member_ids(db: AsyncSession, org_id: uuid.UUID | None) -> list[uuid.UUID]:
    if org_id is None:
        return []
    result = await db.execute(
        select(Annotator.id).where(Annotator.org_id == org_id).order_by(Annotator.id.asc())
    )
    return list(result.scalars().all())


async def setup_consensus(
    db: AsyncSession,
    config_data: ConsensusConfigCreate,
    user: Annotator,
) -> ConsensusConfig:
    pack = await db.get(TaskPack, config_data.task_pack_id)
    if pack is None:
        raise ValueError("Task pack not found")

    existing = await db.execute(
        select(ConsensusConfig).where(ConsensusConfig.task_pack_id == config_data.task_pack_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Consensus is already configured for this task pack")

    tasks = pack.tasks_json or []
    if not tasks:
        raise ValueError("Task pack has no tasks")

    member_ids = await _org_member_ids(db, user.org_id)
    if not member_ids:
        raise ValueError("No annotators in your organization to assign")

    cfg = ConsensusConfig(
        task_pack_id=config_data.task_pack_id,
        annotators_per_task=config_data.annotators_per_task,
        agreement_threshold=config_data.agreement_threshold,
        auto_resolve=config_data.auto_resolve,
        created_by=user.id,
    )
    db.add(cfg)
    await db.flush()

    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        tid = task.get("id")
        if tid is None or not str(tid).strip():
            raise ValueError("Task pack contains a task without id")
        assigned = pick_round_robin_assignees(member_ids, idx, config_data.annotators_per_task)
        ct = ConsensusTask(
            config_id=cfg.id,
            task_pack_id=pack.id,
            task_id=str(tid),
            status="pending",
            assigned_annotators=[str(a) for a in assigned],
            annotations_json={},
        )
        db.add(ct)

    await db.commit()
    await db.refresh(cfg)
    return cfg


def _task_dict_for_pack(pack: TaskPack, task_id: str) -> dict[str, Any] | None:
    for t in pack.tasks_json or []:
        if isinstance(t, dict) and str(t.get("id", "")) == task_id:
            return t
    return None


def _annotator_key(aid: uuid.UUID) -> str:
    return str(aid)


def next_task_priority_row(ct: ConsensusTask, annotator_id: uuid.UUID) -> tuple[int, float]:
    """Higher sort key first: more submissions on this task, then newer tasks last."""
    ann = ct.annotations_json or {}
    subs = len(ann)
    key = _annotator_key(annotator_id)
    if key in ann:
        return (-1, 0.0)
    return (subs, -ct.created_at.timestamp() if ct.created_at else 0.0)


async def get_next_task(
    db: AsyncSession,
    annotator_id: uuid.UUID,
    task_pack_id: uuid.UUID,
) -> AnnotatorNextTaskResponse | None:
    pack = await db.get(TaskPack, task_pack_id)
    if pack is None:
        raise ValueError("Task pack not found")

    result = await db.execute(
        select(ConsensusTask)
        .where(ConsensusTask.task_pack_id == task_pack_id)
        .where(ConsensusTask.status.in_(("pending", "in_progress")))
    )
    rows = list(result.scalars().all())
    aid_str = _annotator_key(annotator_id)
    candidates: list[ConsensusTask] = []
    for ct in rows:
        assigned = ct.assigned_annotators or []
        if aid_str not in assigned:
            continue
        if aid_str in (ct.annotations_json or {}):
            continue
        candidates.append(ct)

    if not candidates:
        return None

    candidates.sort(key=lambda c: next_task_priority_row(c, annotator_id), reverse=True)
    chosen = candidates[0]
    td = _task_dict_for_pack(pack, chosen.task_id) or {"id": chosen.task_id}
    ann = chosen.annotations_json or {}
    assigned = chosen.assigned_annotators or []
    return AnnotatorNextTaskResponse(
        consensus_task_id=chosen.id,
        task_id=chosen.task_id,
        task_data=td,
        annotators_completed=len(ann),
        annotators_required=len(assigned),
    )


async def submit_annotation(
    db: AsyncSession,
    consensus_task_id: uuid.UUID,
    annotator_id: uuid.UUID,
    annotation: dict[str, Any],
) -> ConsensusTask:
    ct = await db.get(ConsensusTask, consensus_task_id)
    if ct is None:
        raise ValueError("Consensus task not found")

    aid = _annotator_key(annotator_id)
    if aid not in (ct.assigned_annotators or []):
        raise ValueError("Not assigned to this consensus task")

    if ct.status in ("agreed", "disputed", "resolved"):
        raise ValueError("This consensus task is already closed")

    pack = await db.get(TaskPack, ct.task_pack_id)
    if pack is None:
        raise ValueError("Task pack not found")
    task_dict = _task_dict_for_pack(pack, ct.task_id) or {}

    merged = dict(ct.annotations_json or {})
    merged[aid] = dict(annotation)
    ct.annotations_json = merged

    if ct.status == "pending":
        ct.status = "in_progress"

    assigned_n = len(ct.assigned_annotators or [])
    if assigned_n > 0 and len(merged) >= assigned_n:
        ct.agreement_score = compute_task_agreement(ct, task_dict)
        await check_and_resolve(db, ct, task_dict)

    await db.commit()
    await db.refresh(ct)
    return ct


async def check_and_resolve(
    db: AsyncSession,
    consensus_task: ConsensusTask,
    task_dict: dict[str, Any],
) -> None:
    cfg = await db.get(ConsensusConfig, consensus_task.config_id)
    if cfg is None:
        return

    score = consensus_task.agreement_score
    if score is None:
        score = compute_task_agreement(consensus_task, task_dict)
        consensus_task.agreement_score = score

    thr = float(cfg.agreement_threshold)
    if score >= thr:
        consensus_task.status = "agreed"
        if cfg.auto_resolve:
            anns = [
                v
                for k, v in sorted((consensus_task.annotations_json or {}).items())
                if isinstance(v, dict)
            ]
            consensus_task.resolved_annotation = build_auto_resolved_annotation(anns, task_dict)
    else:
        consensus_task.status = "disputed"


async def resolve_dispute(
    db: AsyncSession,
    consensus_task_id: uuid.UUID,
    resolver_id: uuid.UUID,
    resolved_annotation: dict[str, Any],
) -> ConsensusTask:
    ct = await db.get(ConsensusTask, consensus_task_id)
    if ct is None:
        raise ValueError("Consensus task not found")
    if ct.status != "disputed":
        raise ValueError("Task is not in disputed status")

    ct.resolved_annotation = dict(resolved_annotation)
    ct.resolved_by = resolver_id
    ct.status = "resolved"
    await db.commit()
    await db.refresh(ct)
    return ct


async def get_status(db: AsyncSession, task_pack_id: uuid.UUID) -> ConsensusStatusResponse:
    cfg_result = await db.execute(
        select(ConsensusConfig).where(ConsensusConfig.task_pack_id == task_pack_id)
    )
    cfg = cfg_result.scalar_one_or_none()
    if cfg is None:
        return ConsensusStatusResponse(
            task_pack_id=task_pack_id,
            total_tasks=0,
            agreed=0,
            disputed=0,
            pending=0,
            in_progress=0,
            resolved=0,
            overall_agreement=None,
        )

    result = await db.execute(select(ConsensusTask).where(ConsensusTask.config_id == cfg.id))
    rows = list(result.scalars().all())

    counts = {"pending": 0, "in_progress": 0, "agreed": 0, "disputed": 0, "resolved": 0}
    scores: list[float] = []
    for r in rows:
        st = r.status
        if st in counts:
            counts[st] += 1
        else:
            counts["pending"] += 1
        if r.agreement_score is not None:
            scores.append(float(r.agreement_score))

    overall = sum(scores) / len(scores) if scores else None

    return ConsensusStatusResponse(
        task_pack_id=task_pack_id,
        total_tasks=len(rows),
        agreed=counts["agreed"],
        disputed=counts["disputed"],
        pending=counts["pending"],
        in_progress=counts["in_progress"],
        resolved=counts["resolved"],
        overall_agreement=overall,
    )


async def list_disputed_tasks(db: AsyncSession, task_pack_id: uuid.UUID) -> list[ConsensusTask]:
    result = await db.execute(
        select(ConsensusTask)
        .where(ConsensusTask.task_pack_id == task_pack_id)
        .where(ConsensusTask.status == "disputed")
        .order_by(ConsensusTask.updated_at.desc())
    )
    return list(result.scalars().all())


def filter_task_read_for_annotator(
    ct: ConsensusTask,
    annotator_id: uuid.UUID,
) -> ConsensusTaskRead:
    """Narrow annotations_json to the current annotator only."""
    key = _annotator_key(annotator_id)
    ann = ct.annotations_json or {}
    subset = {key: ann[key]} if key in ann else {}
    base = ConsensusTaskRead.model_validate(ct)
    return base.model_copy(update={"annotations_json": subset})
