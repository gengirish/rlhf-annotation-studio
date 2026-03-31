from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.models import ReviewAssignment
from tests.conftest import FakeDB, FakeExecuteResult, _statement_sql, make_annotator_row


class FakeReviewDB(FakeDB):
    """FakeDB with review_assignments SELECT support and ReviewAssignment timestamps on refresh."""

    async def refresh(self, obj: object) -> None:
        if type(obj).__name__ == "ReviewAssignment":
            now = datetime.now(UTC)
            if getattr(obj, "id", None) is None:
                obj.id = uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now

    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()
        if "from review_assignments" not in sql_lower.replace("\n", " "):
            return await super().execute(statement)

        assignments = [
            r
            for r in self.rows.values()
            if type(r).__name__ == "ReviewAssignment" or type(r).__name__ == "SimpleNamespace"
        ]
        # Only actual review rows: SimpleNamespace used for pre-seeded assignments has task_id
        assignments = [
            a
            for a in assignments
            if getattr(a, "task_id", None) is not None
            and getattr(a, "task_pack_id", None) is not None
        ]

        m_aid = re.search(r"annotator_id\s*=\s*'([0-9a-f-]{36})'", sql, re.IGNORECASE)
        if m_aid:
            aid = UUID(m_aid.group(1))
            assignments = [a for a in assignments if getattr(a, "annotator_id", None) == aid]

        m_st = re.search(r"review_assignments\.status\s*=\s*'([^']*)'", sql, re.IGNORECASE)
        if m_st:
            st = m_st.group(1)
            assignments = [a for a in assignments if getattr(a, "status", None) == st]

        if "updated_at asc" in sql_lower:
            assignments.sort(
                key=lambda r: getattr(r, "updated_at", datetime.min.replace(tzinfo=UTC)),
            )
        elif "created_at desc" in sql_lower:
            assignments.sort(
                key=lambda r: getattr(r, "created_at", datetime.min.replace(tzinfo=UTC)),
                reverse=True,
            )

        return FakeExecuteResult(scalars_all=assignments)


def make_task_pack_row(
    *,
    pack_id: UUID | None = None,
    tasks_json: list | None = None,
) -> SimpleNamespace:
    pid = pack_id or uuid4()
    tj = tasks_json if tasks_json is not None else [{"id": "t-default"}]
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=pid,
        slug="test-pack",
        name="Test Pack",
        description="",
        language="general",
        task_count=len(tj),
        tasks_json=tj,
        created_at=now,
        updated_at=now,
    )


def make_review_row(
    *,
    assignment_id: UUID | None = None,
    task_pack_id: UUID | None = None,
    task_id: str = "t1",
    annotator_id: UUID | None = None,
    status: str = "assigned",
    annotation_json: dict | None = None,
    reviewer_id: UUID | None = None,
    reviewer_notes: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=assignment_id or uuid4(),
        task_pack_id=task_pack_id or uuid4(),
        task_id=task_id,
        annotator_id=annotator_id or uuid4(),
        status=status,
        annotation_json=annotation_json,
        reviewer_id=reviewer_id,
        reviewer_notes=reviewer_notes,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


@pytest.fixture
def fake_db() -> FakeReviewDB:
    return FakeReviewDB()


def test_assign_review_success(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    pack_id = uuid4()
    annotator_id = uuid4()
    fake_db.rows[pack_id] = make_task_pack_row(pack_id=pack_id)
    fake_db.rows[annotator_id] = SimpleNamespace(id=annotator_id, email="a@example.com")

    client = authed_client(role="reviewer")
    resp = client.post(
        "/api/v1/reviews/assign",
        json={
            "task_pack_id": str(pack_id),
            "task_id": "task-99",
            "annotator_id": str(annotator_id),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_id"] == "task-99"
    assert data["status"] == "assigned"
    assert data["annotator_id"] == str(annotator_id)
    assert fake_db.commits == 1


def test_assign_review_pack_not_found(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    missing_pack = uuid4()
    annotator_id = uuid4()
    fake_db.rows[annotator_id] = SimpleNamespace(id=annotator_id, email="a@example.com")

    client = authed_client(role="reviewer")
    resp = client.post(
        "/api/v1/reviews/assign",
        json={
            "task_pack_id": str(missing_pack),
            "task_id": "task-99",
            "annotator_id": str(annotator_id),
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Task pack not found"


def test_assign_review_annotator_not_found(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    pack_id = uuid4()
    missing_annotator = uuid4()
    fake_db.rows[pack_id] = make_task_pack_row(pack_id=pack_id)

    client = authed_client(role="reviewer")
    resp = client.post(
        "/api/v1/reviews/assign",
        json={
            "task_pack_id": str(pack_id),
            "task_id": "task-99",
            "annotator_id": str(missing_annotator),
        },
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Annotator not found"


def test_assign_review_annotator_role_forbidden(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    pack_id = uuid4()
    annotator_id = uuid4()
    fake_db.rows[pack_id] = make_task_pack_row(pack_id=pack_id)
    fake_db.rows[annotator_id] = SimpleNamespace(id=annotator_id, email="a@example.com")

    client = authed_client(role="annotator")
    resp = client.post(
        "/api/v1/reviews/assign",
        json={
            "task_pack_id": str(pack_id),
            "task_id": "task-99",
            "annotator_id": str(annotator_id),
        },
    )
    assert resp.status_code == 403


def test_bulk_assign_success(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    pack_id = uuid4()
    annotator_id = uuid4()
    fake_db.rows[pack_id] = make_task_pack_row(
        pack_id=pack_id,
        tasks_json=[{"id": "a1"}, {"id": "a2"}, {"id": "a3"}],
    )
    fake_db.rows[annotator_id] = SimpleNamespace(id=annotator_id, email="a@example.com")

    client = authed_client(role="admin")
    resp = client.post(
        "/api/v1/reviews/bulk-assign",
        json={"task_pack_id": str(pack_id), "annotator_id": str(annotator_id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 3
    task_ids = {row["task_id"] for row in data}
    assert task_ids == {"a1", "a2", "a3"}
    assert fake_db.commits == 1


def test_queue_returns_user_assignments(app: FastAPI, fake_db: FakeReviewDB) -> None:
    uid = uuid4()
    other = uuid4()
    pack_id = uuid4()
    ra = make_review_row(annotator_id=uid, task_pack_id=pack_id, task_id="mine")
    rb = make_review_row(annotator_id=other, task_pack_id=pack_id, task_id="theirs")
    fake_db.rows[ra.id] = ra
    fake_db.rows[rb.id] = rb

    user = make_annotator_row(role="annotator")
    user.id = uid

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        resp = client.get("/api/v1/reviews/queue")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["task_id"] == "mine"
    assert items[0]["annotator_id"] == str(uid)


def test_pending_returns_submitted(app: FastAPI, fake_db: FakeReviewDB) -> None:
    pack_id = uuid4()
    r_sub = make_review_row(
        task_pack_id=pack_id,
        task_id="s1",
        status="submitted",
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )
    r_asg = make_review_row(
        task_pack_id=pack_id,
        task_id="s2",
        status="assigned",
    )
    fake_db.rows[r_sub.id] = r_sub
    fake_db.rows[r_asg.id] = r_asg

    client = authed_client_factory(app, role="reviewer")
    resp = client.get("/api/v1/reviews/pending")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "submitted"
    assert items[0]["task_id"] == "s1"


def authed_client_factory(app: FastAPI, *, role: str, org_id: UUID | None = None) -> TestClient:
    user = make_annotator_row(role=role, org_id=org_id)

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    return TestClient(app)


def test_team_returns_all(app: FastAPI, fake_db: FakeReviewDB) -> None:
    pack_id = uuid4()
    r1 = make_review_row(task_pack_id=pack_id, task_id="x1")
    r2 = make_review_row(task_pack_id=pack_id, task_id="x2")
    fake_db.rows[r1.id] = r1
    fake_db.rows[r2.id] = r2

    client = authed_client_factory(app, role="reviewer")
    resp = client.get("/api/v1/reviews/team")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    tids = {i["task_id"] for i in items}
    assert tids == {"x1", "x2"}


def test_team_forbidden_for_annotator(
    app: FastAPI,
    fake_db: FakeReviewDB,
    authed_client: Callable[..., TestClient],
) -> None:
    client = authed_client(role="annotator")
    resp = client.get("/api/v1/reviews/team")
    assert resp.status_code == 403


def test_update_review_success(app: FastAPI, fake_db: FakeReviewDB) -> None:
    assignment_id = uuid4()
    reviewer = make_annotator_row(role="reviewer")
    row = make_review_row(assignment_id=assignment_id, status="submitted")
    fake_db.rows[assignment_id] = row

    async def override_current_user() -> SimpleNamespace:
        return reviewer

    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        resp = client.put(
            f"/api/v1/reviews/{assignment_id}",
            json={"status": "approved", "reviewer_notes": "LGTM"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["reviewer_notes"] == "LGTM"
    assert data["reviewer_id"] == str(reviewer.id)
    assert row.status == "approved"
    assert row.reviewer_notes == "LGTM"
    assert row.reviewer_id == reviewer.id
    assert fake_db.commits == 1


def test_update_review_not_found(app: FastAPI, fake_db: FakeReviewDB) -> None:
    missing = uuid4()
    client = authed_client_factory(app, role="reviewer")
    resp = client.put(
        f"/api/v1/reviews/{missing}",
        json={"status": "rejected", "reviewer_notes": None},
    )
    assert resp.status_code == 404


def test_submit_review_success(app: FastAPI, fake_db: FakeReviewDB) -> None:
    uid = uuid4()
    assignment_id = uuid4()
    row = make_review_row(assignment_id=assignment_id, annotator_id=uid, status="assigned")
    fake_db.rows[assignment_id] = row

    user = make_annotator_row(role="annotator")
    user.id = uid

    async def override_current_user() -> SimpleNamespace:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/reviews/{assignment_id}/submit",
            json={"annotation_json": {"score": 1}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "submitted"
    assert data["annotation_json"] == {"score": 1}
    assert row.status == "submitted"
    assert row.annotation_json == {"score": 1}


def test_submit_review_forbidden(app: FastAPI, fake_db: FakeReviewDB) -> None:
    owner = uuid4()
    assignment_id = uuid4()
    row = make_review_row(assignment_id=assignment_id, annotator_id=owner, status="assigned")
    fake_db.rows[assignment_id] = row

    other = make_annotator_row(role="annotator")

    async def override_current_user() -> SimpleNamespace:
        return other

    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        resp = client.post(
            f"/api/v1/reviews/{assignment_id}/submit",
            json={"annotation_json": {}},
        )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"
