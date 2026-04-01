from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.db import get_db
from app.main import create_app
from tests.conftest import FakeDB, FakeExecuteResult, _statement_sql, _uuids_in_sql


class FakeAuthDB(FakeDB):
    """Extends FakeDB with email-based annotator lookups and work session resolution for auth tests."""

    def __init__(self) -> None:
        super().__init__()
        self._by_email: dict[str, object] = {}

    def add(self, obj: object) -> None:
        super().add(obj)
        email = getattr(obj, "email", None)
        if email:
            self._by_email[str(email).lower()] = obj

    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()

        if "annotator" in sql_lower and "email" in sql_lower:
            for email_key, row in self._by_email.items():
                if email_key in sql_lower:
                    return FakeExecuteResult(scalar_one_or_none_value=row)
            return FakeExecuteResult(scalar_one_or_none_value=None)

        if "work_session" in sql_lower.replace("_", ""):
            uuids = _uuids_in_sql(sql)
            sessions = [
                r
                for r in self.rows.values()
                if type(r).__name__ == "WorkSession"
                and getattr(r, "annotator_id", None) is not None
            ]
            matching = [
                s
                for s in sessions
                if any(getattr(s, "annotator_id", None) == uid for uid in uuids)
            ]
            if not matching:
                return FakeExecuteResult(scalar_one_or_none_value=None)
            matching.sort(
                key=lambda x: getattr(x, "updated_at", datetime.min.replace(tzinfo=UTC)),
                reverse=True,
            )
            return FakeExecuteResult(scalar_one_or_none_value=matching[0])

        return await super().execute(statement)

    async def flush(self) -> None:
        for obj in list(self.rows.values()):
            if getattr(obj, "created_at", None) is None and hasattr(obj, "__table__"):
                obj.created_at = datetime.now(UTC)
            if getattr(obj, "updated_at", None) is None and hasattr(obj, "updated_at"):
                obj.updated_at = datetime.now(UTC)
        await super().flush()

    async def refresh(self, obj: object) -> None:
        if hasattr(obj, "__table__"):
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.now(UTC)
            if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
                obj.updated_at = datetime.now(UTC)
        await super().refresh(obj)


@pytest.fixture
def auth_db() -> FakeAuthDB:
    return FakeAuthDB()


@pytest.fixture
def auth_app(auth_db: FakeAuthDB, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    import app.main as main_module

    async def no_op_warm_pool() -> None:
        return None

    async def override_get_db():
        yield auth_db

    monkeypatch.setattr(main_module, "warm_pool", no_op_warm_pool)
    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


def test_register_success(auth_app: FastAPI) -> None:
    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Alice",
                "email": "alice@example.com",
                "password": "Secret123",
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["annotator"]["name"] == "Alice"
    assert data["annotator"]["email"] == "alice@example.com"
    assert "session_id" in data


def test_register_duplicate_email_returns_409(auth_app: FastAPI, auth_db: FakeAuthDB) -> None:
    existing = SimpleNamespace(
        id=uuid4(),
        name="Bob",
        email="bob@example.com",
        password_hash=hash_password("pass123"),
        phone=None,
        role="annotator",
        org_id=None,
        created_at=datetime.now(UTC),
    )
    auth_db.add(existing)

    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Bob2",
                "email": "bob@example.com",
                "password": "Secret123",
            },
        )
    assert resp.status_code == 409


def test_register_missing_required_fields(auth_app: FastAPI) -> None:
    with TestClient(auth_app) as client:
        resp = client.post("/api/v1/auth/register", json={"name": "Test"})
    assert resp.status_code == 422


def test_register_password_too_short(auth_app: FastAPI) -> None:
    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "name": "Charlie",
                "email": "charlie@example.com",
                "password": "abc",
            },
        )
    assert resp.status_code == 422


def test_login_success(auth_app: FastAPI, auth_db: FakeAuthDB) -> None:
    hashed = hash_password("correct_password")
    user = SimpleNamespace(
        id=uuid4(),
        name="Dave",
        email="dave@example.com",
        password_hash=hashed,
        phone=None,
        role="annotator",
        org_id=None,
        created_at=datetime.now(UTC),
    )
    auth_db.add(user)

    now = datetime.now(UTC)
    session = SimpleNamespace(
        id=uuid4(),
        annotator_id=user.id,
        tasks_json=None,
        annotations_json={},
        task_times_json={},
        active_pack_file=None,
        created_at=now,
        updated_at=now,
    )
    auth_db.rows[session.id] = session

    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "dave@example.com",
                "password": "correct_password",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["annotator"]["email"] == "dave@example.com"
    assert "session_id" in data


def test_login_wrong_password_returns_401(auth_app: FastAPI, auth_db: FakeAuthDB) -> None:
    hashed = hash_password("real_password")
    user = SimpleNamespace(
        id=uuid4(),
        name="Eve",
        email="eve@example.com",
        password_hash=hashed,
        phone=None,
        role="annotator",
        org_id=None,
        created_at=datetime.now(UTC),
    )
    auth_db.add(user)

    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "eve@example.com",
                "password": "wrong_password",
            },
        )
    assert resp.status_code == 401


def test_login_nonexistent_email_returns_401(auth_app: FastAPI) -> None:
    with TestClient(auth_app) as client:
        resp = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "doesnt_matter",
            },
        )
    assert resp.status_code == 401
