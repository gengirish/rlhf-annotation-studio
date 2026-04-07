from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.quality_score import AnnotatorQualityScore
from app.schemas.gold_scoring import GoldScoreResponse, TaskScore
from app.services.quality_service import (
    QualityService,
    drift_alerts_from_windows,
    peer_agreement_for_annotator,
    rank_leaderboard_rows,
    speed_percentile_rank,
    weighted_overall_trust,
)


def test_weighted_trust_all_components_sums_weights() -> None:
    t = weighted_overall_trust(1.0, 1.0, 1.0, 1.0, 1.0)
    assert t is not None
    assert abs(t - 1.0) < 1e-9


def test_weighted_trust_renormalizes_when_partial() -> None:
    # Only gold (0.3 of full); alone it should map to 1.0 after renormalize
    t = weighted_overall_trust(0.5, None, None, None, None)
    assert t is not None
    assert abs(t - 0.5) < 1e-9

    t2 = weighted_overall_trust(0.0, 1.0, None, None, None)
    # weights 0.3 and 0.3 -> (0+1)/2 = 0.5
    assert t2 is not None
    assert abs(t2 - 0.5) < 1e-9


def test_weighted_trust_none_when_no_metrics() -> None:
    assert weighted_overall_trust(None, None, None, None, None) is None


def test_speed_percentile_rank() -> None:
    assert speed_percentile_rank(25.0, [10.0, 20.0, 30.0]) == pytest.approx(1.0 / 3.0)
    # Faster than all peers → all peer times are greater than annotator's
    assert speed_percentile_rank(5.0, [10.0, 20.0]) == pytest.approx(1.0)
    assert speed_percentile_rank(100.0, [10.0, 20.0]) == pytest.approx(0.0)
    assert speed_percentile_rank(None, [1.0]) is None
    assert speed_percentile_rank(1.0, []) is None


def test_drift_warning_and_critical() -> None:
    aid = uuid.uuid4()
    now = datetime.now(UTC)
    w = timedelta(days=7)

    def _row(**kwargs: float) -> AnnotatorQualityScore:
        return AnnotatorQualityScore(
            annotator_id=aid,
            task_pack_id=None,
            computed_at=now,
            gold_accuracy=kwargs.get("gold_accuracy"),  # type: ignore[arg-type]
            agreement_with_experts=kwargs.get("agreement_with_experts"),  # type: ignore[arg-type]
            agreement_with_peers=kwargs.get("agreement_with_peers"),  # type: ignore[arg-type]
            consistency_score=kwargs.get("consistency_score"),  # type: ignore[arg-type]
            speed_percentile=kwargs.get("speed_percentile"),  # type: ignore[arg-type]
            overall_trust_score=kwargs.get("overall_trust_score"),  # type: ignore[arg-type]
        )

    baseline = [_row(overall_trust_score=0.80), _row(overall_trust_score=0.80)]
    recent_warn = [_row(overall_trust_score=0.66)]  # 17.5% drop
    alerts = drift_alerts_from_windows(
        annotator_id=aid,
        annotator_name="A",
        recent_scores=recent_warn,
        baseline_scores=baseline,
    )
    assert any(a.alert_level == "warning" and a.metric == "overall_trust_score" for a in alerts)

    recent_crit = [_row(overall_trust_score=0.50)]  # 37.5% drop
    alerts2 = drift_alerts_from_windows(
        annotator_id=aid,
        annotator_name="A",
        recent_scores=recent_crit,
        baseline_scores=baseline,
    )
    assert any(a.alert_level == "critical" for a in alerts2)


def test_drift_new_annotator_insufficient_history() -> None:
    aid = uuid.uuid4()
    now = datetime.now(UTC)
    one = AnnotatorQualityScore(
        annotator_id=aid,
        task_pack_id=None,
        computed_at=now,
        overall_trust_score=0.9,
    )
    assert not drift_alerts_from_windows(
        annotator_id=aid,
        annotator_name="A",
        recent_scores=[one],
        baseline_scores=[],
    )


def test_leaderboard_ranking_order() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    computed = datetime.now(UTC)
    lb = rank_leaderboard_rows(
        [
            (a, "low", 0.2, 1, 0.1),
            (b, "high", 0.9, 5, 0.95),
            (c, "mid", 0.5, 3, 0.4),
        ],
        computed_at=computed,
    )
    assert lb.annotators[0].annotator_id == b and lb.annotators[0].rank == 1
    assert lb.annotators[1].annotator_id == c
    assert lb.annotators[2].annotator_id == a


def test_peer_agreement_majority() -> None:
    t1 = uuid.uuid4()
    ann_x = uuid.uuid4()
    ann_y = uuid.uuid4()
    rows = [
        {"annotator_id": ann_x, "task_id": "1", "preference": 1, "dimensions": {"d": 2}},
        {"annotator_id": ann_y, "task_id": "1", "preference": 1, "dimensions": {"d": 2}},
        {"annotator_id": t1, "task_id": "1", "preference": 0, "dimensions": {"d": 2}},
    ]
    p = peer_agreement_for_annotator(t1, rows)
    assert p is not None
    assert p == pytest.approx(0.5)  # pref wrong, dim matches majority


@pytest.mark.asyncio
async def test_calibration_pass_fail_uses_threshold() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    pack_id = uuid.uuid4()
    test_id = uuid.uuid4()

    pack = MagicMock()
    pack.tasks_json = [{"id": "t1", "gold": {"preference": 1}}]

    test_row = MagicMock()
    test_row.task_pack_id = pack_id
    test_row.passing_threshold = 0.7

    async def _get(_model: object, key: uuid.UUID) -> object | None:
        if key == test_id:
            return test_row
        if key == pack_id:
            return pack
        return None

    db.get = _get

    gold_fail = GoldScoreResponse(
        total_gold_tasks=1,
        scored_tasks=1,
        overall_accuracy=0.69,
        task_scores=[TaskScore(task_id="t1", overall_score=0.69)],
    )
    gold_pass = GoldScoreResponse(
        total_gold_tasks=1,
        scored_tasks=1,
        overall_accuracy=0.71,
        task_scores=[TaskScore(task_id="t1", overall_score=0.71)],
    )

    svc = QualityService(db)
    with patch("app.services.quality_service.GoldScoringService.score_workspace", return_value=gold_fail):
        att, passed = await svc.attempt_calibration(test_id, uuid.uuid4(), {"t1": {"preference": 2}})
    assert passed is False
    assert att.score == pytest.approx(0.69)

    db.reset_mock()
    db.get = _get
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    with patch("app.services.quality_service.GoldScoringService.score_workspace", return_value=gold_pass):
        _att2, passed2 = await svc.attempt_calibration(test_id, uuid.uuid4(), {"t1": {"preference": 1}})
    assert passed2 is True
