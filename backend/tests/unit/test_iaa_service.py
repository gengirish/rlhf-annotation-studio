"""Unit tests for IAAService agreement metrics."""

from __future__ import annotations

import uuid

import pytest

from app.schemas.iaa import IAAResponse
from app.services.iaa_service import IAAService

A1 = uuid.uuid4()
A2 = uuid.uuid4()
A3 = uuid.uuid4()
PACK = uuid.uuid4()


def _row(task_id: str, annotator_id: uuid.UUID, preference: int | None, dimensions: dict | None = None):
    return {
        "task_id": task_id,
        "annotator_id": annotator_id,
        "preference": preference,
        "dimensions": dimensions or {},
    }


def test_cohens_kappa_perfect_agreement():
    la = [1, 1, 2, 2, 0]
    lb = [1, 1, 2, 2, 0]
    k = IAAService.cohens_kappa_two_raters(la, lb)
    assert k is not None
    assert abs(k - 1.0) < 1e-9


def test_cohens_kappa_known_moderate():
    # Hand-calculated: p_o=0.75, p_e=0.5 -> kappa=0.5
    la = [1, 2, 1, 2]
    lb = [1, 2, 2, 2]
    k = IAAService.cohens_kappa_two_raters(la, lb)
    assert k is not None
    assert abs(k - 0.5) < 1e-9


def test_cohens_kappa_chance_agreement_is_zero():
    # Constructed so p_o == p_e -> κ = 0
    la = [1, 1, 2, 2]
    lb = [1, 2, 1, 2]
    k = IAAService.cohens_kappa_two_raters(la, lb)
    assert k is not None
    assert abs(k) < 1e-9


def test_fleiss_kappa_perfect_three_raters():
    # Same n=3 raters on each of 4 tasks, all choose category 1
    overlap = {
        "t1": {A1: 1, A2: 1, A3: 1},
        "t2": {A1: 1, A2: 1, A3: 1},
        "t3": {A1: 1, A2: 1, A3: 1},
        "t4": {A1: 1, A2: 1, A3: 1},
    }
    f = IAAService.fleiss_kappa(overlap)
    assert f is not None
    assert abs(f - 1.0) < 1e-9


def test_fleiss_kappa_variable_raters_returns_none():
    overlap = {
        "t1": {A1: 1, A2: 1},
        "t2": {A1: 1, A2: 1, A3: 1},
    }
    assert IAAService.fleiss_kappa(overlap) is None


def test_krippendorff_alpha_ordinal_multi_rater():
    # Three raters on shared tasks; ordinal metric should return a finite coefficient
    data = {
        "t1": {A1: 1, A2: 2, A3: 2},
        "t2": {A1: 2, A2: 2, A3: 3},
        "t3": {A1: 1, A2: 1, A3: 2},
    }
    a = IAAService.krippendorff_alpha(data, level="ordinal")
    assert a is not None
    assert -1.01 <= a <= 1.01
    assert isinstance(a, float)


def test_krippendorff_alpha_nominal_perfect():
    overlap = {
        "t1": {A1: 0, A2: 0},
        "t2": {A1: 1, A2: 1},
    }
    a = IAAService.krippendorff_alpha(overlap, level="nominal")
    assert a is not None
    assert abs(a - 1.0) < 1e-9


def test_single_annotator_pairwise_kappa_none():
    overlap = {"t1": {A1: 1}}
    assert IAAService.average_pairwise_cohens_kappa(overlap) is None
    assert IAAService.fleiss_kappa(overlap) is None
    assert IAAService.krippendorff_alpha(overlap, level="nominal") is None


def test_no_overlap_preference_percentage_zero():
    rows = [
        _row("t1", A1, 0),
        _row("t2", A2, 1),
    ]
    resp = IAAService.compute_from_annotations(rows, task_pack_id=PACK)
    assert isinstance(resp, IAAResponse)
    assert resp.preference_agreement is not None
    assert resp.preference_agreement.percentage_agreement == 0.0
    assert resp.preference_agreement.n_items == 0
    assert resp.n_tasks_with_overlap == 0


def test_real_world_like_rlhf_preferences_and_dimensions():
    rows = [
        _row("task-a", A1, 0, {"helpfulness": 4, "accuracy": 3}),
        _row("task-a", A2, 0, {"helpfulness": 4, "accuracy": 4}),
        _row("task-a", A3, 1, {"helpfulness": 3, "accuracy": 3}),
        _row("task-b", A1, 1, {"helpfulness": 5, "accuracy": 5}),
        _row("task-b", A2, 1, {"helpfulness": 4, "accuracy": 5}),
    ]
    resp = IAAService.compute_from_annotations(rows, task_pack_id=PACK)
    assert resp.n_tasks_with_overlap == 2
    assert resp.preference_agreement is not None
    assert resp.preference_agreement.n_items == 2
    assert 0.0 <= resp.preference_agreement.percentage_agreement <= 1.0
    names = {d.dimension for d in resp.dimension_agreements}
    assert names == {"accuracy", "helpfulness"}
    for d in resp.dimension_agreements:
        assert d.n_items >= 1


def test_scotts_pi_two_raters_perfect():
    assert IAAService.scotts_pi_two_raters([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
