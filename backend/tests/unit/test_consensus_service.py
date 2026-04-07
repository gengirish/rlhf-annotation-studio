from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.consensus import ConsensusConfig, ConsensusTask
from app.services.consensus_service import (
    check_and_resolve,
    compute_task_agreement,
    next_task_priority_row,
    pick_round_robin_assignees,
    submit_annotation,
)


def _comparison_task() -> dict:
    return {
        "id": "t1",
        "type": "comparison",
        "dimensions": [{"name": "Security", "scale": 5}],
    }


def test_compute_agreement_unanimous_preference() -> None:
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="t1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2), str(u3)],
        annotations_json={
            str(u1): {"preference": 0},
            str(u2): {"preference": 0},
            str(u3): {"preference": 0},
        },
    )
    assert compute_task_agreement(ct, _comparison_task()) == pytest.approx(1.0)


def test_compute_agreement_split_preference() -> None:
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="t1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2), str(u3)],
        annotations_json={
            str(u1): {"preference": 0},
            str(u2): {"preference": 0},
            str(u3): {"preference": 1},
        },
    )
    assert compute_task_agreement(ct, _comparison_task()) == pytest.approx(2.0 / 3.0)


def test_dimension_mad_agreement_rating_task() -> None:
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    task = {
        "id": "r1",
        "type": "rating",
        "dimensions": [{"name": "Quality", "scale": 5}],
    }
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="r1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2)],
        annotations_json={
            str(u1): {"dimensions": {"Quality": 4}},
            str(u2): {"dimensions": {"Quality": 4}},
        },
    )
    assert compute_task_agreement(ct, task) == pytest.approx(1.0)

    ct2 = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="r1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2)],
        annotations_json={
            str(u1): {"dimensions": {"Quality": 1}},
            str(u2): {"dimensions": {"Quality": 5}},
        },
    )
    # mean=3, mad=2, scale 5 => 1 - 2/(5-1) = 0.5
    assert compute_task_agreement(ct2, task) == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_auto_resolve_when_threshold_met() -> None:
    cfg_id = uuid.uuid4()
    cfg = ConsensusConfig(
        id=cfg_id,
        task_pack_id=uuid.uuid4(),
        annotators_per_task=3,
        agreement_threshold=0.7,
        auto_resolve=True,
        created_by=uuid.uuid4(),
    )
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=cfg_id,
        task_pack_id=uuid.uuid4(),
        task_id="t1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2), str(u3)],
        annotations_json={
            str(u1): {"preference": 1, "justification": "all pick B"},
            str(u2): {"preference": 1},
            str(u3): {"preference": 1},
        },
    )
    ct.agreement_score = compute_task_agreement(ct, _comparison_task())

    db = AsyncMock()

    async def mock_get(model: type, key: uuid.UUID) -> ConsensusConfig | None:
        if model is ConsensusConfig and key == cfg_id:
            return cfg
        return None

    db.get = mock_get

    await check_and_resolve(db, ct, _comparison_task())
    assert ct.status == "agreed"
    assert ct.resolved_annotation is not None
    assert ct.resolved_annotation.get("preference") == 1


@pytest.mark.asyncio
async def test_dispute_when_below_threshold() -> None:
    cfg_id = uuid.uuid4()
    cfg = ConsensusConfig(
        id=cfg_id,
        task_pack_id=uuid.uuid4(),
        annotators_per_task=3,
        agreement_threshold=0.75,
        auto_resolve=True,
        created_by=uuid.uuid4(),
    )
    u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=cfg_id,
        task_pack_id=uuid.uuid4(),
        task_id="t1",
        status="in_progress",
        assigned_annotators=[str(u1), str(u2), str(u3)],
        annotations_json={
            str(u1): {"preference": 0},
            str(u2): {"preference": 0},
            str(u3): {"preference": 1},
        },
    )
    ct.agreement_score = compute_task_agreement(ct, _comparison_task())

    db = AsyncMock()

    async def mock_get(model: type, key: uuid.UUID) -> ConsensusConfig | None:
        if model is ConsensusConfig and key == cfg_id:
            return cfg
        return None

    db.get = mock_get

    await check_and_resolve(db, ct, _comparison_task())
    assert ct.status == "disputed"
    assert ct.resolved_annotation is None


def test_next_task_routing_prioritizes_nearly_complete() -> None:
    annotator = uuid.uuid4()
    ts = datetime(2026, 1, 1, tzinfo=UTC)

    low = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="a",
        status="in_progress",
        assigned_annotators=[str(annotator), str(uuid.uuid4())],
        annotations_json={},
        created_at=ts,
    )

    high = ConsensusTask(
        id=uuid.uuid4(),
        config_id=uuid.uuid4(),
        task_pack_id=uuid.uuid4(),
        task_id="b",
        status="in_progress",
        assigned_annotators=[str(annotator), str(uuid.uuid4()), str(uuid.uuid4())],
        annotations_json={str(uuid.uuid4()): {"preference": 0}},
        created_at=ts,
    )

    ordered = sorted([low, high], key=lambda c: next_task_priority_row(c, annotator), reverse=True)
    assert ordered[0].task_id == "b"


def test_round_robin_assignments_wraps() -> None:
    m = [uuid.uuid4() for _ in range(3)]
    a0 = pick_round_robin_assignees(m, 0, 3)
    a1 = pick_round_robin_assignees(m, 1, 3)
    assert a0 == m
    assert a1 == [m[1], m[2], m[0]]


def test_round_robin_fewer_members_than_requested() -> None:
    m = [uuid.uuid4(), uuid.uuid4()]
    got = pick_round_robin_assignees(m, 0, 5)
    assert got == m


@pytest.mark.asyncio
async def test_submit_annotation_triggers_resolution() -> None:
    cfg_id = uuid.uuid4()
    pack_id = uuid.uuid4()
    cfg = ConsensusConfig(
        id=cfg_id,
        task_pack_id=pack_id,
        annotators_per_task=2,
        agreement_threshold=1.0,
        auto_resolve=False,
        created_by=uuid.uuid4(),
    )
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    ct = ConsensusTask(
        id=uuid.uuid4(),
        config_id=cfg_id,
        task_pack_id=pack_id,
        task_id="t1",
        status="pending",
        assigned_annotators=[str(u1), str(u2)],
        annotations_json={},
    )

    from app.models.task_pack import TaskPack

    pack = TaskPack(
        id=pack_id,
        slug="consensus-pack-test",
        name="P",
        tasks_json=[{"id": "t1", "type": "comparison"}],
    )

    async def fake_get(model: type, eid: uuid.UUID) -> object | None:
        if model is ConsensusTask and eid == ct.id:
            return ct
        if model is TaskPack and eid == pack_id:
            return pack
        if model is ConsensusConfig and eid == cfg_id:
            return cfg
        return None

    db = AsyncMock()
    db.get = fake_get
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    await submit_annotation(db, ct.id, u1, {"preference": 0})
    assert str(u1) in ct.annotations_json
    assert ct.status == "in_progress"

    await submit_annotation(db, ct.id, u2, {"preference": 1})
    assert ct.status == "disputed"
    assert ct.agreement_score == pytest.approx(0.5)
