from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.auth import get_current_user
from tests.conftest import WORKSPACE_PAYLOAD, FakeDB, make_session_row


def test_workspace_read_write_success_for_owner(app: FastAPI, fake_db: FakeDB) -> None:
    owner_id = uuid4()
    session_id = uuid4()
    row = make_session_row(session_id=session_id, annotator_id=owner_id)
    fake_db.rows[session_id] = row

    async def override_current_user() -> SimpleNamespace:
        return SimpleNamespace(id=owner_id)

    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        read_resp = client.get(f"/api/v1/sessions/{session_id}/workspace")
        assert read_resp.status_code == 200
        data = read_resp.json()
        assert data["session_id"] == str(session_id)
        assert data["annotator_id"] == str(owner_id)

        put_resp = client.put(
            f"/api/v1/sessions/{session_id}/workspace",
            json=WORKSPACE_PAYLOAD,
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["ok"] is True

    assert row.tasks_json == [{"id": "t-2"}]
    assert row.annotations_json == {"t-2": {"status": "done"}}
    assert row.task_times_json == {"t-2": 99}
    assert row.active_pack_file == "tasks/code-review-comparisons.json"
    assert fake_db.commits == 1


def test_workspace_access_denied_for_other_user(app: FastAPI, fake_db: FakeDB) -> None:
    owner_id = uuid4()
    other_user_id = uuid4()
    session_id = uuid4()
    fake_db.rows[session_id] = make_session_row(session_id=session_id, annotator_id=owner_id)

    async def override_current_user() -> SimpleNamespace:
        return SimpleNamespace(id=other_user_id)

    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        read_resp = client.get(f"/api/v1/sessions/{session_id}/workspace")
        assert read_resp.status_code == 403

        put_resp = client.put(
            f"/api/v1/sessions/{session_id}/workspace",
            json=WORKSPACE_PAYLOAD,
        )
        assert put_resp.status_code == 403

    assert fake_db.commits == 0


def test_workspace_access_denied_without_token(app: FastAPI, fake_db: FakeDB) -> None:
    session_id = uuid4()
    fake_db.rows[session_id] = make_session_row(session_id=session_id, annotator_id=uuid4())

    with TestClient(app) as client:
        read_resp = client.get(f"/api/v1/sessions/{session_id}/workspace")
        assert read_resp.status_code == 401

        put_resp = client.put(
            f"/api/v1/sessions/{session_id}/workspace",
            json=WORKSPACE_PAYLOAD,
        )
        assert put_resp.status_code == 401


def test_workspace_session_not_found_returns_404(app: FastAPI) -> None:
    async def override_current_user() -> SimpleNamespace:
        return SimpleNamespace(id=uuid4())

    app.dependency_overrides[get_current_user] = override_current_user
    missing_session_id = uuid4()

    with TestClient(app) as client:
        read_resp = client.get(f"/api/v1/sessions/{missing_session_id}/workspace")
        assert read_resp.status_code == 404

        put_resp = client.put(
            f"/api/v1/sessions/{missing_session_id}/workspace",
            json=WORKSPACE_PAYLOAD,
        )
        assert put_resp.status_code == 404


def test_workspace_put_rejects_invalid_payload_shape(app: FastAPI, fake_db: FakeDB) -> None:
    owner_id = uuid4()
    session_id = uuid4()
    fake_db.rows[session_id] = make_session_row(session_id=session_id, annotator_id=owner_id)

    async def override_current_user() -> SimpleNamespace:
        return SimpleNamespace(id=owner_id)

    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        put_resp = client.put(
            f"/api/v1/sessions/{session_id}/workspace",
            json={
                "tasks": [{"id": "t-2"}],
                "annotations": ["not-a-dict"],
                "task_times": {"t-2": 99},
                "active_pack_file": "tasks/code-review-comparisons.json",
            },
        )
        assert put_resp.status_code == 422

    assert fake_db.commits == 0


def test_workspace_invalid_token_returns_401(app: FastAPI, fake_db: FakeDB) -> None:
    session_id = uuid4()
    fake_db.rows[session_id] = make_session_row(session_id=session_id, annotator_id=uuid4())

    async def invalid_token_user() -> SimpleNamespace:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    app.dependency_overrides[get_current_user] = invalid_token_user

    with TestClient(app) as client:
        read_resp = client.get(f"/api/v1/sessions/{session_id}/workspace")
        assert read_resp.status_code == 401

        put_resp = client.put(
            f"/api/v1/sessions/{session_id}/workspace",
            json=WORKSPACE_PAYLOAD,
        )
        assert put_resp.status_code == 401
