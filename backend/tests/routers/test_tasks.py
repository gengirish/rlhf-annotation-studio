from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user, get_current_user_or_api_key
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
_LIMIT_RE = re.compile(r"\sLIMIT\s+(\d+)", re.IGNORECASE)
_OFFSET_RE = re.compile(r"\sOFFSET\s+(\d+)", re.IGNORECASE)
_LIKE_PATTERN_RE = re.compile(r"LIKE\s+'%%?([^%']+)%%?'", re.IGNORECASE)
_LANG_EQ_RE = re.compile(r"lower\(task_packs\.language\)\s*=\s*'([^']*)'", re.IGNORECASE)


def _slug_filter_from_sql(sql: str) -> str | None:
    m = _TASK_PACK_SLUG_EQ.search(sql)
    return m.group(1) if m else None


def _is_search_query(sql: str) -> bool:
    return bool(_LIKE_PATTERN_RE.search(sql)) and "count(" not in sql.lower()


def _extract_search_filters(sql: str) -> tuple[str, str | None]:
    m = _LIKE_PATTERN_RE.search(sql)
    pattern = m.group(1) if m else ""
    lang_m = _LANG_EQ_RE.search(sql)
    lang = lang_m.group(1) if lang_m else None
    return pattern, lang


class FakeTaskDB(FakeDB):
    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()
        if "task_packs" in sql_lower:
            if "count(" in sql_lower:
                total = sum(1 for r in self.rows.values() if getattr(r, "slug", None) is not None)
                return FakeExecuteResult(scalar_one_value=total)
            wanted = _slug_filter_from_sql(sql)
            if wanted is not None:
                for row in self.rows.values():
                    slug = getattr(row, "slug", None)
                    if slug == wanted:
                        return FakeExecuteResult(scalar_one_or_none_value=row)
                return FakeExecuteResult(scalar_one_or_none_value=None)

            all_packs = [
                r for r in self.rows.values() if getattr(r, "slug", None) is not None
            ]

            if _is_search_query(sql):
                pattern, lang_filter = _extract_search_filters(sql)
                p = pattern.lower()
                if "cast" in sql_lower:
                    filtered = [
                        r for r in all_packs
                        if p in str(getattr(r, "tasks_json", "") or "").lower()
                    ]
                else:
                    filtered = [
                        r for r in all_packs
                        if p in (getattr(r, "name", "") or "").lower()
                        or p in (getattr(r, "slug", "") or "").lower()
                        or p in (getattr(r, "description", "") or "").lower()
                    ]
                if lang_filter:
                    filtered = [
                        r for r in filtered
                        if (getattr(r, "language", "") or "").lower() == lang_filter
                    ]
                filtered.sort(
                    key=lambda r: (
                        (getattr(r, "name", "") or "").lower(),
                        (getattr(r, "slug", "") or "").lower(),
                    )
                )
                limit_match = _LIMIT_RE.search(sql)
                limit = int(limit_match.group(1)) if limit_match else len(filtered)
                return FakeExecuteResult(scalars_all=filtered[:limit])

            packs = list(all_packs)
            packs.sort(
                key=lambda r: (
                    (getattr(r, "name", "") or "").lower(),
                    (getattr(r, "slug", "") or "").lower(),
                )
            )
            limit_match = _LIMIT_RE.search(sql)
            offset_match = _OFFSET_RE.search(sql)
            limit = int(limit_match.group(1)) if limit_match else len(packs)
            offset = int(offset_match.group(1)) if offset_match else 0
            packs = packs[offset : offset + limit]
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
    assert resp.json() == {
        "packs": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }


def test_list_packs_with_data(client: TestClient, fake_db: FakeTaskDB) -> None:
    b = _make_task_pack(slug="b-pack", name="B Pack")
    a = _make_task_pack(slug="a-pack", name="A Pack")
    fake_db.add(b)
    fake_db.add(a)
    resp = client.get("/api/v1/tasks/packs")
    assert resp.status_code == 200
    slugs = [p["slug"] for p in resp.json()["packs"]]
    assert slugs == ["a-pack", "b-pack"]
    assert resp.json()["total"] == 2
    assert resp.json()["has_more"] is False


def test_list_packs_pagination(client: TestClient, fake_db: FakeTaskDB) -> None:
    fake_db.add(_make_task_pack(slug="c-pack", name="C Pack"))
    fake_db.add(_make_task_pack(slug="a-pack", name="A Pack"))
    fake_db.add(_make_task_pack(slug="b-pack", name="B Pack"))

    resp = client.get("/api/v1/tasks/packs?limit=2&offset=1")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [p["slug"] for p in body["packs"]]
    assert slugs == ["b-pack", "c-pack"]
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert body["has_more"] is False


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


def test_create_pack_requires_admin(authed_client) -> None:
    client = authed_client(role="annotator")
    payload = {
        "slug": "new-pack",
        "name": "New Pack",
        "description": "Desc",
        "language": "python",
        "tasks_json": [VALID_TASK],
    }
    resp = client.post("/api/v1/tasks/packs", json=payload)
    assert resp.status_code == 403


def test_create_pack_success(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client(role="admin")
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
    client = authed_client(role="admin")
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


def test_update_pack_requires_admin(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client(role="annotator")
    fake_db.add(_make_task_pack(slug="existing", name="Existing"))
    resp = client.put(
        "/api/v1/tasks/packs/existing",
        json={"name": "Updated"},
    )
    assert resp.status_code == 403


def test_delete_pack_requires_admin(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client(role="annotator")
    fake_db.add(_make_task_pack(slug="no-delete", name="No"))
    resp = client.delete("/api/v1/tasks/packs/no-delete")
    assert resp.status_code == 403


def test_delete_pack_success(authed_client, fake_db: FakeTaskDB) -> None:
    client = authed_client(role="admin")
    pack = _make_task_pack(slug="to-delete", name="X")
    fake_db.add(pack)
    pid = pack.id
    resp = client.delete("/api/v1/tasks/packs/to-delete")
    assert resp.status_code == 204
    assert pid not in fake_db.rows


def test_delete_pack_not_found(authed_client) -> None:
    client = authed_client(role="admin")
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
    app.dependency_overrides[get_current_user_or_api_key] = override_current_user
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


def test_search_empty_query(client: TestClient) -> None:
    resp = client.get("/api/v1/tasks/search?q=")
    assert resp.status_code == 200
    body = resp.json()
    assert body["packs"] == []
    assert body["tasks"] == []
    assert body["total_packs"] == 0
    assert body["total_tasks"] == 0


def test_search_packs_by_name(client: TestClient, fake_db: FakeTaskDB) -> None:
    fake_db.add(_make_task_pack(slug="py-debug", name="Python Debugging", language="python"))
    fake_db.add(_make_task_pack(slug="java-debug", name="Java Debugging", language="java"))
    fake_db.add(_make_task_pack(slug="safety-eval", name="Safety Evaluation", language="general"))

    resp = client.get("/api/v1/tasks/search?q=debug")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_packs"] == 2
    slugs = [p["slug"] for p in body["packs"]]
    assert "py-debug" in slugs
    assert "java-debug" in slugs
    assert "safety-eval" not in slugs


def test_search_packs_with_language_filter(client: TestClient, fake_db: FakeTaskDB) -> None:
    fake_db.add(_make_task_pack(slug="py-debug", name="Python Debugging", language="python"))
    fake_db.add(_make_task_pack(slug="java-debug", name="Java Debugging", language="java"))

    resp = client.get("/api/v1/tasks/search?q=debug&language=python")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_packs"] == 1
    assert body["packs"][0]["slug"] == "py-debug"


def test_search_deep_task_match(client: TestClient, fake_db: FakeTaskDB) -> None:
    tasks = [
        {**VALID_TASK, "id": "t-api", "title": "API Design Review", "type": "rating", "prompt": "Rate this API"},
        {**VALID_TASK, "id": "t-bug", "title": "Bug Fix Analysis", "type": "comparison", "prompt": "Compare fixes"},
    ]
    fake_db.add(_make_task_pack(slug="code-review", name="Code Reviews", tasks_json=tasks))
    fake_db.add(_make_task_pack(slug="safety", name="Safety Pack"))

    resp = client.get("/api/v1/tasks/search?q=API")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tasks"] >= 1
    api_hits = [t for t in body["tasks"] if t["task_id"] == "t-api"]
    assert len(api_hits) == 1
    assert api_hits[0]["pack_slug"] == "code-review"
    assert api_hits[0]["task_index"] == 0


def test_search_deep_task_with_type_filter(client: TestClient, fake_db: FakeTaskDB) -> None:
    tasks = [
        {**VALID_TASK, "id": "t-api", "title": "API Design Review", "type": "rating", "prompt": "Rate this API"},
        {**VALID_TASK, "id": "t-cmp", "title": "API Comparison", "type": "comparison", "prompt": "Compare API approaches"},
    ]
    fake_db.add(_make_task_pack(slug="mixed", name="Mixed Tasks", tasks_json=tasks))

    resp = client.get("/api/v1/tasks/search?q=API&task_type=comparison")
    assert resp.status_code == 200
    body = resp.json()
    task_ids = [t["task_id"] for t in body["tasks"]]
    assert "t-cmp" in task_ids
    assert "t-api" not in task_ids


def test_search_no_results(client: TestClient, fake_db: FakeTaskDB) -> None:
    fake_db.add(_make_task_pack(slug="py-debug", name="Python Debugging"))

    resp = client.get("/api/v1/tasks/search?q=nonexistent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_packs"] == 0
    assert body["total_tasks"] == 0
