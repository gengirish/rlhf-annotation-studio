from __future__ import annotations

import re
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.db import get_db
from app.main import create_app

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _statement_sql(statement: object) -> str:
    try:
        from sqlalchemy.dialects import postgresql

        return str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
    except Exception:
        return str(statement)


def _uuids_in_sql(sql: str) -> list[UUID]:
    return [UUID(m) for m in _UUID_RE.findall(sql)]


class FakeScalars:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)


class FakeExecuteResult:
    """Mimics a subset of SQLAlchemy `Result` for router tests."""

    def __init__(
        self,
        *,
        scalar_one_value: int | None = 0,
        scalar_one_or_none_value: Any | None = None,
        scalars_all: list[Any] | None = None,
    ) -> None:
        self._scalar_one = scalar_one_value
        self._scalar_optional = scalar_one_or_none_value
        self._scalars_all = list(scalars_all) if scalars_all is not None else []

    def scalar_one(self) -> Any:
        return self._scalar_one

    def scalar_one_or_none(self) -> Any:
        return self._scalar_optional

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._scalars_all)


class FakeDB:
    """Async session test double with SQLAlchemy-like methods."""

    def __init__(self) -> None:
        self.rows: dict[UUID, Any] = {}
        self.commits = 0
        self._workspace_revisions: list[Any] = []

    async def get(self, _model: object, key: UUID) -> Any | None:
        return self.rows.get(key)

    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()

        if "count" in sql_lower and "workspace_revision" in sql_lower.replace("_", ""):
            uuids = _uuids_in_sql(sql)
            if uuids:
                sid = uuids[0]
                n = sum(
                    1
                    for r in self._workspace_revisions
                    if getattr(r, "session_id", None) == sid
                )
                return FakeExecuteResult(scalar_one_value=n)
            return FakeExecuteResult(scalar_one_value=len(self._workspace_revisions))

        if (
            "workspace_revision" in sql_lower.replace("_", "")
            and "count" not in sql_lower
        ):
            uuids = _uuids_in_sql(sql)
            if uuids:
                sid = uuids[0]
                matching = [r for r in self._workspace_revisions if r.session_id == sid]
                matching.sort(
                    key=lambda r: getattr(r, "created_at", datetime.min.replace(tzinfo=UTC)),
                    reverse=True,
                )
                return FakeExecuteResult(scalars_all=matching)

        if "annotator" in sql_lower and "count" not in sql_lower:
            for uid in _uuids_in_sql(sql):
                row = self.rows.get(uid)
                if row is not None and type(row).__name__ == "Annotator":
                    return FakeExecuteResult(scalar_one_or_none_value=row)
            for uid in _uuids_in_sql(sql):
                row = self.rows.get(uid)
                if row is not None and getattr(row, "email", None) is not None:
                    return FakeExecuteResult(scalar_one_or_none_value=row)

        return FakeExecuteResult()

    def add(self, obj: Any) -> None:
        if getattr(obj, "id", None) is None and hasattr(obj, "__table__"):
            obj.id = uuid4()
        oid = getattr(obj, "id", None)
        if oid is not None:
            self.rows[oid] = obj
        if type(obj).__name__ == "WorkspaceRevision":
            self._workspace_revisions.append(obj)

    def delete(self, obj: Any) -> None:
        oid = getattr(obj, "id", None)
        if oid is not None and oid in self.rows:
            del self.rows[oid]
        if obj in self._workspace_revisions:
            self._workspace_revisions.remove(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj: object) -> None:
        return None


def make_annotator_row(*, role: str = "annotator", org_id: UUID | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        org_id=org_id,
        name="Test User",
        email="test@example.com",
        phone=None,
        created_at=datetime.now(UTC),
    )


def make_session_row(*, session_id: UUID, annotator_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=session_id,
        annotator_id=annotator_id,
        tasks_json=[{"id": "t-1"}],
        annotations_json={"t-1": {"status": "done"}},
        task_times_json={"t-1": 12},
        active_pack_file="tasks/debugging-exercises-python.json",
        updated_at=datetime.now(UTC),
    )


WORKSPACE_PAYLOAD = {
    "tasks": [{"id": "t-2"}],
    "annotations": {"t-2": {"status": "done"}},
    "task_times": {"t-2": 99},
    "active_pack_file": "tasks/code-review-comparisons.json",
}


@pytest.fixture
def fake_db() -> FakeDB:
    return FakeDB()


@pytest.fixture
def app(fake_db: FakeDB, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    import app.main as main_module

    async def no_op_warm_pool() -> None:
        return None

    async def override_get_db() -> AsyncGenerator[FakeDB, None]:
        yield fake_db

    monkeypatch.setattr(main_module, "warm_pool", no_op_warm_pool)
    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
def authed_client(app: FastAPI) -> Callable[..., TestClient]:
    def _factory(*, role: str = "annotator", org_id: UUID | None = None) -> TestClient:
        user = make_annotator_row(role=role, org_id=org_id)

        async def override_current_user() -> SimpleNamespace:
            return user

        app.dependency_overrides[get_current_user] = override_current_user
        return TestClient(app)

    return _factory
