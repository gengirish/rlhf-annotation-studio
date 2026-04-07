from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import ROLE_ADMIN, ROLE_REVIEWER
from app.models.annotator import Annotator
from app.models.quality_score import AnnotatorQualityScore, CalibrationAttempt, CalibrationTest
from app.models.review_assignment import ReviewAssignment
from app.models.task_pack import TaskPack
from app.models.work_session import WorkSession
from app.models.workspace_revision import WorkspaceRevision
from app.schemas.quality import (
    AnnotatorQualityEntry,
    CalibrationTestCreate,
    QualityDashboard,
    QualityDriftAlert,
    QualityLeaderboard,
    QualityScoreRead,
)
from app.services.gold_scoring_service import GoldScoringService
from app.services.metrics_service import _numeric_task_times

WEIGHT_GOLD = 0.3
WEIGHT_EXPERT = 0.3
WEIGHT_PEER = 0.2
WEIGHT_CONSISTENCY = 0.1
WEIGHT_SPEED = 0.1

STATUS_SUBMITTED = "submitted"
STATUS_APPROVED = "approved"
_REVIEW_OK = frozenset({STATUS_SUBMITTED, STATUS_APPROVED})


def weighted_overall_trust(
    gold_accuracy: float | None,
    agreement_with_experts: float | None,
    agreement_with_peers: float | None,
    consistency_score: float | None,
    speed_percentile: float | None,
) -> float | None:
    """Weighted composite; missing components are omitted and weights renormalized to sum to 1.0."""
    parts: list[tuple[float, float]] = []
    if gold_accuracy is not None:
        parts.append((WEIGHT_GOLD, gold_accuracy))
    if agreement_with_experts is not None:
        parts.append((WEIGHT_EXPERT, agreement_with_experts))
    if agreement_with_peers is not None:
        parts.append((WEIGHT_PEER, agreement_with_peers))
    if consistency_score is not None:
        parts.append((WEIGHT_CONSISTENCY, consistency_score))
    if speed_percentile is not None:
        parts.append((WEIGHT_SPEED, speed_percentile))
    if not parts:
        return None
    wsum = sum(w for w, _ in parts)
    if wsum <= 0:
        return None
    return sum(w * v for w, v in parts) / wsum


def speed_percentile_rank(
    annotator_avg_time: float | None, peer_avg_times: list[float]
) -> float | None:
    """
    Fraction of peers strictly slower (higher time) than this annotator.
    Faster annotators get higher percentiles in [0, 1].
    """
    if annotator_avg_time is None:
        return None
    peers = [p for p in peer_avg_times if p is not None and p > 0]
    if not peers:
        return None
    slower = sum(1 for p in peers if p > annotator_avg_time)
    return slower / len(peers)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _annotation_flat_agreement(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    parts: list[float] = []
    pa, pb = a.get("preference"), b.get("preference")
    if isinstance(pa, int) and isinstance(pb, int):
        parts.append(1.0 if pa == pb else 0.0)
    da = a.get("dimensions")
    db = b.get("dimensions")
    if isinstance(da, dict) and isinstance(db, dict):
        for k in set(da) & set(db):
            va, vb = da.get(k), db.get(k)
            if isinstance(va, int) and isinstance(vb, int):
                parts.append(1.0 if va == vb else 0.0)
    if not parts:
        return None
    return float(mean(parts))


def _payload_from_assignment(row: ReviewAssignment) -> dict[str, Any]:
    raw = row.annotation_json if isinstance(row.annotation_json, dict) else {}
    return dict(raw)


def peer_agreement_for_annotator(
    target_id: uuid.UUID, iaa_rows: list[dict[str, Any]]
) -> float | None:
    """How often the target matches per-task majority labels (preference + dimensions)."""
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in iaa_rows:
        by_task[str(r["task_id"])].append(r)

    scores: list[float] = []
    for _tid, group in by_task.items():
        if len(group) < 2:
            continue
        target_rows = [g for g in group if g["annotator_id"] == target_id]
        if not target_rows:
            continue
        trow = target_rows[-1]

        prefs = [g["preference"] for g in group if isinstance(g.get("preference"), int)]
        if len(prefs) >= 2:
            mode_p = max(set(prefs), key=prefs.count)
            tp = trow.get("preference")
            if isinstance(tp, int):
                scores.append(1.0 if tp == mode_p else 0.0)

        dim_keys: set[str] = set()
        for g in group:
            dims = g.get("dimensions")
            if isinstance(dims, dict):
                dim_keys.update(dims.keys())
        for dk in dim_keys:
            vals: list[int] = []
            for g in group:
                dims = g.get("dimensions")
                if isinstance(dims, dict) and isinstance(dims.get(dk), int):
                    vals.append(int(dims[dk]))
            if len(vals) < 2:
                continue
            mode_d = max(set(vals), key=vals.count)
            td = trow.get("dimensions")
            if isinstance(td, dict) and isinstance(td.get(dk), int):
                scores.append(1.0 if int(td[dk]) == mode_d else 0.0)

    return float(mean(scores)) if scores else None


def _review_rows_to_iaa(assignments: Iterable[ReviewAssignment]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in assignments:
        payload = _payload_from_assignment(row)
        pref = payload.get("preference")
        dims = payload.get("dimensions")
        out.append(
            {
                "annotator_id": row.annotator_id,
                "task_id": row.task_id,
                "preference": pref if isinstance(pref, int) else None,
                "dimensions": dims if isinstance(dims, dict) else {},
            },
        )
    return out


def drift_alerts_from_windows(
    *,
    annotator_id: uuid.UUID,
    annotator_name: str,
    recent_scores: list[AnnotatorQualityScore],
    baseline_scores: list[AnnotatorQualityScore],
) -> list[QualityDriftAlert]:
    """
    Compare mean metrics between two rolling windows of stored score snapshots.
    """
    metrics = (
        "gold_accuracy",
        "agreement_with_experts",
        "agreement_with_peers",
        "consistency_score",
        "speed_percentile",
        "overall_trust_score",
    )

    def _avg(rows: list[AnnotatorQualityScore], key: str) -> float | None:
        vals = [getattr(r, key) for r in rows]
        nums = [v for v in vals if isinstance(v, int | float)]
        if not nums:
            return None
        return float(mean(nums))

    alerts: list[QualityDriftAlert] = []
    if not recent_scores or not baseline_scores:
        return alerts

    for m in metrics:
        cur = _avg(recent_scores, m)
        prev = _avg(baseline_scores, m)
        if cur is None or prev is None:
            continue
        if prev <= 0 and cur <= 0:
            continue
        base = prev if prev > 0 else 1e-9
        rel_drop = (prev - cur) / base
        if rel_drop <= 0:
            continue
        level = "critical" if rel_drop > 0.30 else "warning" if rel_drop > 0.15 else None
        if level is None:
            continue
        alerts.append(
            QualityDriftAlert(
                annotator_id=annotator_id,
                annotator_name=annotator_name,
                metric=m,
                previous_value=prev,
                current_value=cur,
                drift_magnitude=_clamp01(rel_drop),
                alert_level=level,
            ),
        )
    return alerts


def rank_leaderboard_rows(
    rows: list[tuple[uuid.UUID, str, float | None, int, float | None]],
    *,
    computed_at: datetime,
) -> QualityLeaderboard:
    """Sort by trust desc (None last), then tasks_completed desc, assign rank."""
    sorted_rows = sorted(
        rows,
        key=lambda x: (
            x[2] is None,
            -(x[2] if x[2] is not None else -1.0),
            -x[3],
        ),
    )
    entries: list[AnnotatorQualityEntry] = []
    for i, (aid, name, trust, n_done, gold) in enumerate(sorted_rows, start=1):
        entries.append(
            AnnotatorQualityEntry(
                annotator_id=aid,
                annotator_name=name,
                overall_trust_score=trust,
                tasks_completed=n_done,
                gold_accuracy=gold,
                rank=i,
            ),
        )
    return QualityLeaderboard(annotators=entries, computed_at=computed_at)


class QualityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _org_member_ids(self, org_id: uuid.UUID) -> list[uuid.UUID]:
        r = await self.db.execute(select(Annotator.id).where(Annotator.org_id == org_id))
        return list(r.scalars().all())

    async def _load_org_review_assignments(
        self,
        org_id: uuid.UUID,
        task_pack_id: uuid.UUID | None,
    ) -> list[ReviewAssignment]:
        q = (
            select(ReviewAssignment)
            .join(Annotator, ReviewAssignment.annotator_id == Annotator.id)
            .where(Annotator.org_id == org_id)
            .where(ReviewAssignment.status.in_(_REVIEW_OK))
            .where(ReviewAssignment.annotation_json.is_not(None))
        )
        if task_pack_id is not None:
            q = q.where(ReviewAssignment.task_pack_id == task_pack_id)
        res = await self.db.execute(q)
        return list(res.scalars().all())

    async def _merge_sessions_workspace(
        self,
        annotator_id: uuid.UUID,
        task_pack_id: uuid.UUID | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
        r = await self.db.execute(
            select(WorkSession)
            .where(WorkSession.annotator_id == annotator_id)
            .order_by(WorkSession.updated_at.asc()),
        )
        sessions = list(r.scalars().all())

        merged_ann: dict[str, Any] = {}
        latest_tasks: list[dict[str, Any]] | None = None
        for s in sessions:
            ann = s.annotations_json if isinstance(s.annotations_json, dict) else {}
            merged_ann.update(ann)
            if s.tasks_json is not None and isinstance(s.tasks_json, list):
                latest_tasks = list(s.tasks_json)

        tasks_list = latest_tasks or []
        allowed: set[str] | None = None
        if task_pack_id is not None:
            pack = await self.db.get(TaskPack, task_pack_id)
            if pack is None:
                tasks_list = []
                merged_ann = {}
            else:
                allowed = set()
                for t in pack.tasks_json or []:
                    if isinstance(t, dict) and t.get("id") is not None:
                        allowed.add(str(t["id"]))
                tasks_list = [
                    t for t in tasks_list if isinstance(t, dict) and str(t.get("id", "")) in allowed
                ]
                merged_ann = {k: v for k, v in merged_ann.items() if k in allowed}

        done = 0
        for _tid, payload in merged_ann.items():
            if isinstance(payload, dict) and payload.get("status") == "done":
                done += 1

        return tasks_list, merged_ann, done

    def _mean_session_time(self, session: WorkSession) -> float | None:
        tt = session.task_times_json if isinstance(session.task_times_json, dict) else {}
        times = _numeric_task_times(tt)
        if not times:
            return None
        return float(mean(times))

    async def _annotator_mean_time(self, annotator_id: uuid.UUID) -> float | None:
        r = await self.db.execute(
            select(WorkSession).where(WorkSession.annotator_id == annotator_id)
        )
        sessions = list(r.scalars().all())
        avgs = [m for s in sessions if (m := self._mean_session_time(s)) is not None]
        return float(mean(avgs)) if avgs else None

    async def _expert_agreement(
        self,
        annotator_id: uuid.UUID,
        org_id: uuid.UUID,
        task_pack_id: uuid.UUID | None,
    ) -> float | None:
        rows = await self._load_org_review_assignments(org_id, task_pack_id)
        by_key: dict[tuple[uuid.UUID, str], list[tuple[uuid.UUID, str, dict[str, Any]]]] = (
            defaultdict(list)
        )
        for row in rows:
            a = await self.db.get(Annotator, row.annotator_id)
            role = a.role if a else ROLE_ADMIN
            by_key[(row.task_pack_id, row.task_id)].append(
                (row.annotator_id, role, _payload_from_assignment(row))
            )

        agreements: list[float] = []
        for (_pack_id, _tid), group in by_key.items():
            mine = [g for g in group if g[0] == annotator_id]
            if not mine:
                continue
            experts = [
                g for g in group if g[1] in (ROLE_REVIEWER, ROLE_ADMIN) and g[0] != annotator_id
            ]
            if not experts:
                continue
            payload_m = mine[-1][2]
            payload_e = experts[-1][2]
            a = _annotation_flat_agreement(payload_m, payload_e)
            if a is not None:
                agreements.append(a)
        return float(mean(agreements)) if agreements else None

    async def compute_consistency(self, annotator_id: uuid.UUID) -> float | None:
        r = await self.db.execute(
            select(WorkspaceRevision)
            .where(WorkspaceRevision.annotator_id == annotator_id)
            .order_by(WorkspaceRevision.created_at.asc()),
        )
        revs = list(r.scalars().all())
        last_by_task: dict[str, dict[str, Any]] = {}
        comparisons: list[float] = []
        for rev in revs:
            snap = rev.annotations_snapshot if isinstance(rev.annotations_snapshot, dict) else {}
            for tid, payload in snap.items():
                if not isinstance(payload, dict):
                    continue
                if payload.get("status") != "done":
                    continue
                if tid in last_by_task:
                    prev = last_by_task[tid]
                    a = _annotation_flat_agreement(prev, payload)
                    if a is not None:
                        comparisons.append(a)
                last_by_task[tid] = dict(payload)
        return float(mean(comparisons)) if comparisons else None

    async def compute_annotator_score(
        self,
        annotator_id: uuid.UUID,
        task_pack_id: uuid.UUID | None = None,
    ) -> QualityScoreRead:
        annotator = await self.db.get(Annotator, annotator_id)
        if annotator is None:
            raise ValueError("Annotator not found")
        org_id = annotator.org_id
        if org_id is None:
            org_id_expert_peer = None
        else:
            org_id_expert_peer = org_id

        tasks_list, merged_ann, tasks_done = await self._merge_sessions_workspace(
            annotator_id, task_pack_id
        )

        gold_svc = GoldScoringService()
        gold_resp = gold_svc.score_workspace(tasks_list, merged_ann)
        gold_accuracy = gold_resp.overall_accuracy if gold_resp.total_gold_tasks > 0 else None

        agreement_experts: float | None = None
        agreement_peers: float | None = None
        if org_id_expert_peer is not None:
            agreement_experts = await self._expert_agreement(
                annotator_id, org_id_expert_peer, task_pack_id
            )
            review_rows = await self._load_org_review_assignments(org_id_expert_peer, task_pack_id)
            iaa_rows = _review_rows_to_iaa(review_rows)
            agreement_peers = peer_agreement_for_annotator(annotator_id, iaa_rows)

        consistency = await self.compute_consistency(annotator_id)

        my_time = await self._annotator_mean_time(annotator_id)
        speed_pct: float | None = None
        if org_id_expert_peer is not None:
            member_ids = await self._org_member_ids(org_id_expert_peer)
            peer_times: list[float] = []
            for mid in member_ids:
                if mid == annotator_id:
                    continue
                t = await self._annotator_mean_time(mid)
                if t is not None:
                    peer_times.append(t)
            speed_pct = speed_percentile_rank(my_time, peer_times)

        if org_id_expert_peer is not None:
            cal_ok = await self.check_calibration_required(annotator_id, org_id_expert_peer)
        else:
            cal_ok = True

        overall = weighted_overall_trust(
            gold_accuracy,
            agreement_experts,
            agreement_peers,
            consistency,
            speed_pct,
        )

        now = datetime.now(UTC)
        details: dict[str, Any] = {
            "gold": gold_resp.model_dump(mode="json"),
            "mean_session_time": my_time,
        }

        row = AnnotatorQualityScore(
            annotator_id=annotator_id,
            task_pack_id=task_pack_id,
            gold_accuracy=gold_accuracy,
            agreement_with_experts=agreement_experts,
            agreement_with_peers=agreement_peers,
            consistency_score=consistency,
            speed_percentile=speed_pct,
            overall_trust_score=overall,
            tasks_completed=tasks_done,
            calibration_passed=cal_ok,
            details_json=details,
            computed_at=now,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)

        return QualityScoreRead.model_validate(row)

    async def compute_leaderboard(self, org_id: uuid.UUID) -> QualityLeaderboard:
        member_ids = await self._org_member_ids(org_id)
        if not member_ids:
            return QualityLeaderboard(annotators=[], computed_at=datetime.now(UTC))

        r = await self.db.execute(
            select(AnnotatorQualityScore, Annotator.name)
            .join(Annotator, AnnotatorQualityScore.annotator_id == Annotator.id)
            .where(Annotator.org_id == org_id)
            .where(AnnotatorQualityScore.task_pack_id.is_(None))
            .order_by(AnnotatorQualityScore.computed_at.desc()),
        )
        raw_rows = r.all()
        best: dict[uuid.UUID, tuple[AnnotatorQualityScore, str]] = {}
        for score_row, name in raw_rows:
            aid = score_row.annotator_id
            if aid not in best:
                best[aid] = (score_row, name)

        computed_at = datetime.now(UTC)
        triples: list[tuple[uuid.UUID, str, float | None, int, float | None]] = []
        for aid in member_ids:
            if aid in best:
                s, nm = best[aid]
                triples.append((aid, nm, s.overall_trust_score, s.tasks_completed, s.gold_accuracy))
            else:
                ann = await self.db.get(Annotator, aid)
                nm = ann.name if ann else str(aid)
                triples.append((aid, nm, None, 0, None))

        return rank_leaderboard_rows(triples, computed_at=computed_at)

    async def detect_drift(
        self, annotator_id: uuid.UUID, window_days: int = 7
    ) -> list[QualityDriftAlert]:
        ann = await self.db.get(Annotator, annotator_id)
        if ann is None:
            return []

        now = datetime.now(UTC)
        window = timedelta(days=window_days)
        recent_start = now - window
        prior_end = recent_start
        prior_start = now - 2 * window

        r = await self.db.execute(
            select(AnnotatorQualityScore)
            .where(AnnotatorQualityScore.annotator_id == annotator_id)
            .where(AnnotatorQualityScore.task_pack_id.is_(None))
            .order_by(AnnotatorQualityScore.computed_at.asc()),
        )
        history = list(r.scalars().all())
        if len(history) < 2:
            return []

        recent = [x for x in history if x.computed_at >= recent_start]
        prior_window = [x for x in history if prior_start <= x.computed_at < prior_end]
        if not recent:
            return []
        if not prior_window:
            prior_window = [x for x in history if x.computed_at < recent_start]

        if not prior_window:
            return []

        return drift_alerts_from_windows(
            annotator_id=annotator_id,
            annotator_name=ann.name,
            recent_scores=recent,
            baseline_scores=prior_window,
        )

    async def create_calibration_test(
        self, data: CalibrationTestCreate, user: Annotator
    ) -> CalibrationTest:
        pack = await self.db.get(TaskPack, data.task_pack_id)
        if pack is None:
            raise ValueError("Task pack not found")
        row = CalibrationTest(
            org_id=user.org_id,
            name=data.name.strip(),
            task_pack_id=data.task_pack_id,
            passing_threshold=data.passing_threshold,
            is_required=data.is_required,
            created_by=user.id,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def attempt_calibration(
        self,
        test_id: uuid.UUID,
        annotator_id: uuid.UUID,
        annotations: dict[str, Any],
    ) -> tuple[CalibrationAttempt, bool]:
        test = await self.db.get(CalibrationTest, test_id)
        if test is None:
            raise ValueError("Calibration test not found")
        pack = await self.db.get(TaskPack, test.task_pack_id)
        if pack is None:
            raise ValueError("Task pack not found")

        gold_svc = GoldScoringService()
        gs = gold_svc.score_workspace(pack.tasks_json or [], annotations)
        score = float(gs.overall_accuracy)
        passed = score >= float(test.passing_threshold)
        details = {
            "gold_response": gs.model_dump(mode="json"),
        }
        attempt = CalibrationAttempt(
            test_id=test_id,
            annotator_id=annotator_id,
            score=score,
            passed=passed,
            details_json=details,
        )
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(attempt)
        return attempt, passed

    async def check_calibration_required(self, annotator_id: uuid.UUID, org_id: uuid.UUID) -> bool:
        r = await self.db.execute(
            select(CalibrationTest).where(
                CalibrationTest.is_required.is_(True),
                or_(CalibrationTest.org_id.is_(None), CalibrationTest.org_id == org_id),
            ),
        )
        required = list(r.scalars().all())
        if not required:
            return True

        for t in required:
            r2 = await self.db.execute(
                select(CalibrationAttempt)
                .where(
                    CalibrationAttempt.test_id == t.id,
                    CalibrationAttempt.annotator_id == annotator_id,
                )
                .order_by(desc(CalibrationAttempt.attempted_at))
                .limit(1),
            )
            last = r2.scalar_one_or_none()
            if last is None or not last.passed:
                return False
        return True

    async def list_calibration_tests_for_org(
        self, org_id: uuid.UUID | None
    ) -> list[CalibrationTest]:
        q = select(CalibrationTest).order_by(CalibrationTest.created_at.desc())
        r = await self.db.execute(q)
        all_rows = list(r.scalars().all())
        if org_id is None:
            return [x for x in all_rows if x.org_id is None]
        return [x for x in all_rows if x.org_id is None or x.org_id == org_id]

    async def calibration_attempts_for_test(self, test_id: uuid.UUID) -> list[CalibrationAttempt]:
        r = await self.db.execute(
            select(CalibrationAttempt)
            .where(CalibrationAttempt.test_id == test_id)
            .order_by(desc(CalibrationAttempt.attempted_at)),
        )
        return list(r.scalars().all())

    async def latest_score_read(
        self,
        annotator_id: uuid.UUID,
        task_pack_id: uuid.UUID | None = None,
    ) -> QualityScoreRead | None:
        q = select(AnnotatorQualityScore).where(AnnotatorQualityScore.annotator_id == annotator_id)
        if task_pack_id is not None:
            q = q.where(AnnotatorQualityScore.task_pack_id == task_pack_id)
        else:
            q = q.where(AnnotatorQualityScore.task_pack_id.is_(None))
        q = q.order_by(desc(AnnotatorQualityScore.computed_at)).limit(1)
        r = await self.db.execute(q)
        row = r.scalar_one_or_none()
        return QualityScoreRead.model_validate(row) if row else None

    async def build_dashboard(self, org_id: uuid.UUID) -> QualityDashboard:
        lb = await self.compute_leaderboard(org_id)
        trusts = [e.overall_trust_score for e in lb.annotators if e.overall_trust_score is not None]
        org_avg = float(mean(trusts)) if trusts else 0.0
        total = len(lb.annotators)

        member_ids = await self._org_member_ids(org_id)
        alerts: list[QualityDriftAlert] = []
        for aid in member_ids:
            alerts.extend(await self.detect_drift(aid, window_days=7))

        r = await self.db.execute(
            select(CalibrationAttempt)
            .join(Annotator, CalibrationAttempt.annotator_id == Annotator.id)
            .where(Annotator.org_id == org_id),
        )
        attempts = list(r.scalars().all())
        pass_rate: float | None = None
        if attempts:
            passed_n = sum(1 for a in attempts if a.passed)
            pass_rate = passed_n / len(attempts)

        return QualityDashboard(
            leaderboard=lb,
            drift_alerts=alerts,
            org_average_trust=org_avg,
            total_annotators=total,
            calibration_pass_rate=pass_rate,
        )
