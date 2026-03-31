from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.auth import ROLE_ADMIN
from tests.conftest import (
    FakeDB,
    FakeExecuteResult,
    _statement_sql,
    _uuids_in_sql,
)


def make_org_row(
    *,
    org_id: UUID | None = None,
    name: str = "Acme",
    slug: str = "acme",
    plan_tier: str = "free",
    stripe_customer_id: str | None = None,
    max_seats: int = 5,
    max_packs: int = 3,
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=org_id or uuid4(),
        name=name,
        slug=slug,
        plan_tier=plan_tier,
        stripe_customer_id=stripe_customer_id,
        max_seats=max_seats,
        max_packs=max_packs,
        created_at=now,
        updated_at=now,
    )


def _is_org_like(row: object) -> bool:
    return getattr(row, "slug", None) is not None and getattr(row, "plan_tier", None) is not None


def _is_annotator_like(row: object) -> bool:
    return getattr(row, "email", None) is not None and not _is_org_like(row)


class FakeOrgDB(FakeDB):
    """FakeDB with Organization slug, Annotator email, and org member listing support."""

    def __init__(self) -> None:
        super().__init__()
        self._by_email: dict[str, object] = {}

    def add(self, obj: object) -> None:
        super().add(obj)
        email = getattr(obj, "email", None)
        if email:
            self._by_email[str(email).lower()] = obj

    async def refresh(self, obj: object) -> None:
        now = datetime.now(UTC)
        if hasattr(obj, "__table__"):
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
                obj.updated_at = now
            if type(obj).__name__ == "Organization":
                if getattr(obj, "plan_tier", None) is None:
                    obj.plan_tier = "free"
                if getattr(obj, "max_seats", None) is None:
                    obj.max_seats = 5
                if getattr(obj, "max_packs", None) is None:
                    obj.max_packs = 3
        await super().refresh(obj)

    async def execute(self, statement: object) -> FakeExecuteResult:
        sql = _statement_sql(statement)
        sql_lower = sql.lower()

        slug_m = re.search(r"organizations\.slug\s*=\s*'([^']*)'", sql, re.IGNORECASE)
        if slug_m is not None:
            want = slug_m.group(1)
            for row in self.rows.values():
                if _is_org_like(row) and getattr(row, "slug", None) == want:
                    return FakeExecuteResult(scalar_one_or_none_value=row)
            return FakeExecuteResult(scalar_one_or_none_value=None)

        if "annotators" in sql_lower and re.search(
            r"where\s+.*annotators\.org_id\s*=",
            sql_lower,
        ):
            uuids = _uuids_in_sql(sql)
            annotators = [r for r in self.rows.values() if _is_annotator_like(r)]
            matching: list[object] = []
            for uid in uuids:
                cand = [a for a in annotators if getattr(a, "org_id", None) == uid]
                if cand:
                    matching = cand
                    break
            matching.sort(
                key=lambda a: (getattr(a, "name", "") or "").lower(),
            )
            return FakeExecuteResult(scalars_all=matching)

        if "annotator" in sql_lower and "email" in sql_lower:
            for email_key, row in self._by_email.items():
                if email_key in sql_lower:
                    return FakeExecuteResult(scalar_one_or_none_value=row)
            return FakeExecuteResult(scalar_one_or_none_value=None)

        return await super().execute(statement)


@pytest.fixture
def fake_db() -> FakeOrgDB:
    return FakeOrgDB()


API_ORGS = "/api/v1/orgs"


def test_create_org_success(
    fake_db: FakeOrgDB,
    authed_client,
) -> None:
    client = authed_client(role="annotator", org_id=None)
    resp = client.post(
        API_ORGS,
        json={"name": "Acme Corp", "slug": "acme-corp"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"
    assert "id" in data
    assert fake_db.commits >= 1


def test_create_org_duplicate_slug_returns_409(
    fake_db: FakeOrgDB,
    authed_client,
) -> None:
    existing = make_org_row(slug="taken-slug", name="Existing")
    fake_db.rows[existing.id] = existing

    client = authed_client(role="annotator", org_id=None)
    resp = client.post(
        API_ORGS,
        json={"name": "Other", "slug": "taken-slug"},
    )
    assert resp.status_code == 409


def test_get_org_success(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row(name="Member Org", slug="member-org")
    fake_db.rows[org.id] = org
    client = authed_client(role="annotator", org_id=org.id)
    resp = client.get(f"{API_ORGS}/{org.id}")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "member-org"


def test_get_org_non_member_returns_403(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row()
    fake_db.rows[org.id] = org
    other_org = uuid4()
    client = authed_client(role="annotator", org_id=other_org)
    resp = client.get(f"{API_ORGS}/{org.id}")
    assert resp.status_code == 403


def test_get_org_not_found_returns_404(authed_client) -> None:
    missing = uuid4()
    client = authed_client(role="annotator", org_id=missing)
    resp = client.get(f"{API_ORGS}/{missing}")
    assert resp.status_code == 404


def test_update_org_admin_success(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row(name="Old", slug="old")
    fake_db.rows[org.id] = org
    client = authed_client(role=ROLE_ADMIN, org_id=org.id)
    resp = client.put(f"{API_ORGS}/{org.id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert org.name == "New Name"


def test_update_org_non_admin_returns_403(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row()
    fake_db.rows[org.id] = org
    client = authed_client(role="annotator", org_id=org.id)
    resp = client.put(f"{API_ORGS}/{org.id}", json={"name": "Hax"})
    assert resp.status_code == 403


def test_add_member_success(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row(slug="with-members")
    fake_db.rows[org.id] = org
    invitee = SimpleNamespace(
        id=uuid4(),
        name="Invitee",
        email="invitee@example.com",
        phone=None,
        role="annotator",
        org_id=None,
        created_at=datetime.now(UTC),
    )
    fake_db.rows[invitee.id] = invitee
    fake_db._by_email["invitee@example.com"] = invitee

    client = authed_client(role=ROLE_ADMIN, org_id=org.id)
    resp = client.post(
        f"{API_ORGS}/{org.id}/members",
        json={"email": "invitee@example.com"},
    )
    assert resp.status_code == 201
    assert invitee.org_id == org.id
    assert resp.json()["email"] == "invitee@example.com"


def test_add_member_not_found_returns_404(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row()
    fake_db.rows[org.id] = org
    client = authed_client(role=ROLE_ADMIN, org_id=org.id)
    resp = client.post(
        f"{API_ORGS}/{org.id}/members",
        json={"email": "nobody@example.com"},
    )
    assert resp.status_code == 404


def test_update_role_admin_success(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row()
    fake_db.rows[org.id] = org
    member = SimpleNamespace(
        id=uuid4(),
        name="Member",
        email="member@example.com",
        phone=None,
        role="annotator",
        org_id=org.id,
        created_at=datetime.now(UTC),
    )
    fake_db.rows[member.id] = member

    client = authed_client(role=ROLE_ADMIN, org_id=org.id)
    resp = client.put(
        f"{API_ORGS}/{org.id}/members/{member.id}/role",
        json={"role": "reviewer"},
    )
    assert resp.status_code == 200
    assert member.role == "reviewer"
    assert resp.json()["role"] == "reviewer"


def test_update_role_non_admin_returns_403(fake_db: FakeOrgDB, authed_client) -> None:
    org = make_org_row()
    fake_db.rows[org.id] = org
    member = SimpleNamespace(
        id=uuid4(),
        name="Member",
        email="m2@example.com",
        phone=None,
        role="annotator",
        org_id=org.id,
        created_at=datetime.now(UTC),
    )
    fake_db.rows[member.id] = member

    client = authed_client(role="annotator", org_id=org.id)
    resp = client.put(
        f"{API_ORGS}/{org.id}/members/{member.id}/role",
        json={"role": "reviewer"},
    )
    assert resp.status_code == 403
