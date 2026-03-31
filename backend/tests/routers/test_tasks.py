from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.models.task_pack import TaskPack
from tests.conftest import FakeDB, FakeExecuteResult, _statement_sql, make_annotator_row

VALID_TASK = {
    "id": "t-1",
    "type": "rating",
    "title": "Test Task",
    "prompt": "Test prompt",
    "responses": [{"label": "A", "text": "Response text"}],
    "dimensions": [{"name": "Accuracy", "description": "How accurate", "scale": 5}],
}

_TASK_PACK_SLUG_EQ = re.compile(r"task_packs\.slug\s*=\s*'([^']*)'", re.IGNORECASE)


def _slug_filter_from_sql(sql: str) -> str | None:
    m = _TASK_PACK_SLUG_EQ.search(sql)
    return m.group(1) if m else None


class FakeTaskDB(FakeDB):
    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()
        if "task_packs" in sql_lower:
            wanted = _slug_filter_from_sql(sql)
            if wanted is not None:
                for row in self.rows.values():
                    slug = getattr(row, "slug", None)
                    if slug == wanted:
                        return FakeExecuteResult(scalar_one_or_none_value=row)
                return FakeExecuteResult(scalar_one_or_none_value=None)
            packs = [
                r
                for r in self.rows.values()
                if getattr(r, "slug", None) is not None
            ]
            packs.sort(key=lambda r: (getattr(r, "name", "") or "").lower())
            return FakeExecuteResult(scalars_all=packs)
        return await super().execute(statement)

    async def delete(self, obj: object) -> None:
        FakeDB.delete(self, obj)

    async def refresh(self, obj: object) -> None:
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(UTC)
        await super().refresh(obj)


def _make_task_pack(
    *,
    slug: str,
    name: str,
    description: str = "",
    language: str = "general",
    tasks_json: list | None = None,
) -> TaskPack:
    now = datetime.now(UTC)
    return TaskPack(
        id=uuid4(),
        slug=slug,
        name=name,
        description=description,
        language=language,
        task_count=len(tasks_json or []),
        tasks_json=tasks_json or [dict(VALID_TASK)],
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def fake_db() -> FakeTaskDB:
    return FakeTaskDB()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_validate_valid_tasks(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/tasks/validate",
        json={"tasks": [VALID_TASK], "strict_mode": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["total_tasks"] == 1
    assert data["valid_tasks"] == 1
    assert data["issues"] == []


def test_validate_invalid_tasks(client: TestClient) -> None:
    bad = {
        "id": "bad",
        "type": "rating",
        "title": "T",
        "prompt": "P",
        "responses": [{"label": "A", "text": "x"}],
        "dimensions": [],
    }
    resp = client.post(
        "/api/v1/tasks/validate",
        json={"tasks": [bad], "strict_mode": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_tasks"] == 0
    assert len(data["issues"]) >= 1
    assert any("dimensions" in i["message"].lower() for i in data["issues"])


def test_list_packs_empty(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/packs")
    assert resp.status_code == 200
    assert resp.json() == {"packs": []}


def test_list_packs_with_data(client: TestClient, fake_db: FakeTaskDB) -> None:
    b = _make_task_pack(slug="b-pack", name="B Pack")
    a = _make_task_pack(slug="a-pack", name="A Pack")
    fake_db.add(b)
    fake_db.add(a)
    resp = client.get("/api/v1/tasks/packs")
    assert resp.status_code == 200
    slugs = [p["slug"] for p in resp.json()["packs"]]
    assert slugs == ["a-pack", "b-pack"]


def test_get_pack_by_slug(client: TestClient, fake_db: FakeTaskDB) -> None:
    pack = _make_task_pack(slug="my-pack", name="My Pack", tasks_json=[dict(VALID_TASK)])
    fake_db.add(pack)
    resp = client.get("/api/v1/tasks/packs/my-pack")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "my-pack"
    assert body["name"] == "My Pack"
    assert body["tasks_json"] == [VALID_TASK]


def test_get_pack_not_found(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/packs/does-not-exist")
    assert resp.status_code == 404


def test_create_pack_success(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client()
    payload = {
        "slug": "new-pack",
        "name": "New Pack",
        "description": "Desc",
        "language": "python",
        "tasks_json": [VALID_TASK],
    }
    resp = client.post("/api/v1/tasks/packs", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "new-pack"
    assert body["task_count"] == 1
    assert body["tasks_json"] == [VALID_TASK]
    assert fake_db.commits >= 1


def test_create_pack_duplicate_slug(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client()
    fake_db.add(_make_task_pack(slug="taken", name="Taken"))
    payload = {
        "slug": "taken",
        "name": "Other",
        "description": "",
        "language": "general",
        "tasks_json": [VALID_TASK],
    }
    resp = client.post("/api/v1/tasks/packs", json=payload)
    assert resp.status_code == 409


def test_delete_pack_success(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client()
    pack = _make_task_pack(slug="to-delete", name="X")
    fake_db.add(pack)
    pid = pack.id
    resp = client.delete("/api/v1/tasks/packs/to-delete")
    assert resp.status_code == 204
    assert pid not in fake_db.rows


def test_delete_pack_not_found(authed_client) -> None:
    client = authed_client()
    resp = client.delete("/api/v1/tasks/packs/missing")
    assert resp.status_code == 404


def test_score_session(fake_db: FakeTaskDB, app: FastAPI) -> None:
    user = make_annotator_row()
    session_id = uuid4()
    tasks_json = [
        {
            "id": "t-gold",
            "type": "comparison",
            "title": "Gold task",
            "prompt": "Pick",
            "responses": [
                {"label": "A", "text": "a"},
                {"label": "B", "text": "b"},
            ],
            "dimensions": [{"name": "Accuracy", "description": "d", "scale": 5}],
            "gold": {"preference": 1, "dimensions": {"Accuracy": 4}},
        }
    ]
    annotations_json = {"t-gold": {"preference": 1, "dimensions": {"Accuracy": 4}}}
    session = SimpleNamespace(
        id=session_id,
        annotator_id=user.id,
        tasks_json=tasks_json,
        annotations_json=annotations_json,
        task_times_json={},
        active_pack_file=None,
        updated_at=datetime.now(UTC),
    )
    fake_db.rows[session_id] = session

    async def override_current_user():
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    resp = client.post(
        "/api/v1/tasks/score-session",
        json={"session_id": str(session_id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_gold_tasks"] == 1
    assert data["scored_tasks"] == 1
    assert data["overall_accuracy"] == 1.0
    assert data["task_scores"][0]["preference_correct"] is True
