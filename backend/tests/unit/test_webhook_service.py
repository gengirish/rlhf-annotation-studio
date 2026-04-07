from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.services.webhook_service import (
    canonical_webhook_body_bytes,
    deliver,
    endpoint_subscribes_to,
    handle_failure,
    sign_webhook_body,
    verify_webhook_signature,
)


def test_hmac_sign_and_verify_round_trip() -> None:
    secret = "whsec_test_secret"
    body = {
        "event": "annotation.submitted",
        "payload": {"task_id": "t1"},
        "timestamp": "2026-04-04T12:00:00Z",
        "webhook_id": str(uuid.uuid4()),
    }
    body_bytes = canonical_webhook_body_bytes(body)
    sig = sign_webhook_body(body_bytes, secret)
    assert len(sig) == 64
    assert verify_webhook_signature(body_bytes, secret, sig)
    assert not verify_webhook_signature(body_bytes, secret, sig + "00")
    assert not verify_webhook_signature(body_bytes, "wrong", sig)


def test_hmac_uses_sha256() -> None:
    secret = "s"
    body_bytes = b'{"a":1}'
    expected = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    assert sign_webhook_body(body_bytes, secret) == expected


def test_event_filtering_subscription() -> None:
    assert endpoint_subscribes_to(["annotation.submitted"], "annotation.submitted")
    assert not endpoint_subscribes_to(["review.completed"], "annotation.submitted")
    assert not endpoint_subscribes_to([], "annotation.submitted")
    assert not endpoint_subscribes_to(None, "annotation.submitted")


@pytest.mark.asyncio
async def test_handle_failure_disables_after_ten() -> None:
    endpoint = WebhookEndpoint(
        id=uuid.uuid4(),
        org_id=None,
        owner_id=uuid.uuid4(),
        url="https://example.com/hook",
        secret="x",
        events=["dataset.exported"],
        is_active=True,
        failure_count=9,
    )
    delivery = WebhookDelivery(
        id=uuid.uuid4(),
        endpoint_id=endpoint.id,
        event="dataset.exported",
        payload_json={},
    )
    db = AsyncMock()
    await handle_failure(db, endpoint, delivery)
    assert endpoint.failure_count == 10
    assert endpoint.is_active is False
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_failure_does_not_disable_below_ten() -> None:
    endpoint = WebhookEndpoint(
        id=uuid.uuid4(),
        org_id=None,
        owner_id=uuid.uuid4(),
        url="https://example.com/hook",
        secret="x",
        events=["dataset.exported"],
        is_active=True,
        failure_count=3,
    )
    delivery = WebhookDelivery(
        id=uuid.uuid4(),
        endpoint_id=endpoint.id,
        event="dataset.exported",
        payload_json={},
    )
    db = AsyncMock()
    await handle_failure(db, endpoint, delivery)
    assert endpoint.failure_count == 4
    assert endpoint.is_active is True


def test_payload_structure_for_signing() -> None:
    endpoint_id = uuid.uuid4()
    body = {
        "event": "review.approved",
        "payload": {"pack_id": str(uuid.uuid4())},
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "webhook_id": str(endpoint_id),
    }
    raw = json.loads(canonical_webhook_body_bytes(body).decode("utf-8"))
    assert raw["event"] == "review.approved"
    assert "payload" in raw
    assert raw["webhook_id"] == str(endpoint_id)
    assert "timestamp" in raw


@pytest.mark.asyncio
async def test_deliver_success_resets_failure_count() -> None:
    endpoint = WebhookEndpoint(
        id=uuid.uuid4(),
        org_id=None,
        owner_id=uuid.uuid4(),
        url="https://example.com/hook",
        secret="whsec",
        events=["test.ping"],
        is_active=True,
        failure_count=5,
    )

    class FakeResponse:
        status_code = 200
        text = '{"ok":true}'

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            headers = kwargs.get("headers") or {}
            assert "X-Webhook-Signature" in headers
            body_bytes = kwargs.get("content")
            assert body_bytes is not None
            loaded = json.loads(body_bytes.decode("utf-8"))
            assert loaded["event"] == "dataset.created"
            assert loaded["payload"] == {"id": "d1"}
            assert loaded["webhook_id"] == str(endpoint.id)
            sig = sign_webhook_body(body_bytes, endpoint.secret)
            assert headers["X-Webhook-Signature"] == sig
            return FakeResponse()

    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with patch("app.services.webhook_service.httpx.AsyncClient", FakeClient):
        await deliver(db, endpoint, "dataset.created", {"id": "d1"})

    assert endpoint.failure_count == 0
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
