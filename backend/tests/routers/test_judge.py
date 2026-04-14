from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeDB, FakeExecuteResult, _statement_sql


@pytest.fixture
def _patch_judge_db(fake_db: FakeDB, monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    """Seed the FakeDB with LLM evaluation rows and wire up execute()."""
    pack_id = uuid4()
    evals: list[SimpleNamespace] = [
        SimpleNamespace(
            id=uuid4(),
            task_pack_id=pack_id,
            task_id=f"task-{i}",
            judge_model="gpt-4o",
            evaluation_json={"preference": 1, "reasoning": "A is better", "dimensions": {"clarity": 7}},
            confidence=0.85,
            human_override=None,
            status="pending" if i % 2 == 0 else "accepted",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        for i in range(5)
    ]

    original_execute = fake_db.execute

    async def patched_execute(statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement).lower()
        if "llm_evaluations" in sql:
            if "count" in sql:
                if "'pending'" in sql:
                    return FakeExecuteResult(scalar_one_value=sum(1 for e in evals if e.status == "pending"))
                return FakeExecuteResult(scalar_one_value=len(evals))
            if "'pending'" in sql:
                return FakeExecuteResult(scalars_all=[e for e in evals if e.status == "pending"])
            return FakeExecuteResult(scalars_all=evals)
        return await original_execute(statement)

    monkeypatch.setattr(fake_db, "execute", patched_execute)
    return evals


class TestListAllEvaluations:
    def test_reviewer_can_list(
        self, authed_client: Callable[..., TestClient], _patch_judge_db: list[SimpleNamespace]
    ) -> None:
        client = authed_client(role="reviewer")
        resp = client.get("/api/v1/judge/evaluations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_admin_can_list(
        self, authed_client: Callable[..., TestClient], _patch_judge_db: list[SimpleNamespace]
    ) -> None:
        client = authed_client(role="admin")
        resp = client.get("/api/v1/judge/evaluations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    def test_annotator_cannot_list(
        self, authed_client: Callable[..., TestClient], _patch_judge_db: list[SimpleNamespace]
    ) -> None:
        client = authed_client(role="annotator")
        resp = client.get("/api/v1/judge/evaluations")
        assert resp.status_code == 403

    def test_status_filter(
        self, authed_client: Callable[..., TestClient], _patch_judge_db: list[SimpleNamespace]
    ) -> None:
        client = authed_client(role="reviewer")
        resp = client.get("/api/v1/judge/evaluations?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # indices 0, 2, 4

    def test_pagination_params(
        self, authed_client: Callable[..., TestClient], _patch_judge_db: list[SimpleNamespace]
    ) -> None:
        client = authed_client(role="admin")
        resp = client.get("/api/v1/judge/evaluations?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 2
        assert data["offset"] == 0
