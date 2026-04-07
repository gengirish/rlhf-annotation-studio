from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.annotator import Annotator
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.schemas.webhook import WebhookCreate


def canonical_webhook_body_bytes(body: dict[str, Any]) -> bytes:
    """Serialize webhook JSON body for signing (stable key order)."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sign_webhook_body(body_bytes: bytes, secret: str) -> str:
    """Return hex-encoded HMAC-SHA256 of body_bytes."""
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


def verify_webhook_signature(body_bytes: bytes, secret: str, signature_hex: str) -> bool:
    """Constant-time compare of HMAC-SHA256 hex digest."""
    expected = sign_webhook_body(body_bytes, secret)
    return hmac.compare_digest(expected, signature_hex)


def endpoint_subscribes_to(events: list[str] | None, event: str) -> bool:
    return bool(events) and event in events


def _utc_timestamp_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _payload_to_jsonable(payload: Any) -> dict[str, Any]:
    raw = json.loads(json.dumps(payload, default=str))
    if isinstance(raw, dict):
        return raw
    return {"value": raw}


async def register_endpoint(
    db: AsyncSession, owner: Annotator, data: WebhookCreate
) -> WebhookEndpoint:
    secret = secrets.token_urlsafe(32)
    row = WebhookEndpoint(
        org_id=owner.org_id,
        owner_id=owner.id,
        url=data.url.strip(),
        secret=secret,
        events=list(data.events),
        is_active=data.is_active,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def handle_failure(
    db: AsyncSession, endpoint: WebhookEndpoint, delivery: WebhookDelivery
) -> None:
    endpoint.failure_count += 1
    if endpoint.failure_count >= 10:
        endpoint.is_active = False
    await db.flush()


async def deliver(
    db: AsyncSession, endpoint: WebhookEndpoint, event: str, payload: Any
) -> WebhookDelivery:
    body: dict[str, Any] = {
        "event": event,
        "payload": payload,
        "timestamp": _utc_timestamp_iso(),
        "webhook_id": str(endpoint.id),
    }
    body_bytes = canonical_webhook_body_bytes(body)
    signature = sign_webhook_body(body_bytes, endpoint.secret)

    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event=event,
        payload_json=_payload_to_jsonable(payload),
        success=False,
        attempts=1,
    )
    db.add(delivery)
    await db.flush()

    t0 = time.perf_counter()
    response_status: int | None = None
    response_body: str | None = None
    ok = False

    timeout = httpx.Timeout(10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                endpoint.url,
                content=body_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature,
                },
            )
        response_status = resp.status_code
        text = resp.text or ""
        response_body = text[:1000] if text else None
        ok = 200 <= resp.status_code < 300
    except httpx.TimeoutException:
        response_body = "timeout"
    except httpx.RequestError as exc:
        response_body = str(exc)[:1000]

    duration_ms = int((time.perf_counter() - t0) * 1000)
    delivery.response_status = response_status
    delivery.response_body = response_body
    delivery.success = ok
    delivery.duration_ms = duration_ms

    endpoint.last_triggered_at = datetime.now(UTC)
    if ok:
        endpoint.failure_count = 0
    else:
        await handle_failure(db, endpoint, delivery)

    await db.commit()
    await db.refresh(delivery)
    return delivery


async def dispatch_event(db: AsyncSession, org_id: UUID | None, event: str, payload: Any) -> None:
    stmt = select(WebhookEndpoint).where(WebhookEndpoint.is_active.is_(True))
    if org_id is not None:
        stmt = stmt.where(WebhookEndpoint.org_id == org_id)
    else:
        stmt = stmt.where(WebhookEndpoint.org_id.is_(None))

    result = await db.execute(stmt)
    candidates = list(result.scalars().all())
    endpoint_ids = [e.id for e in candidates if endpoint_subscribes_to(e.events, event)]

    async def _one(eid: UUID) -> None:
        async with AsyncSessionLocal() as session:
            ep = await session.get(WebhookEndpoint, eid)
            if ep is None or not ep.is_active:
                return
            if not endpoint_subscribes_to(ep.events, event):
                return
            await deliver(session, ep, event, payload)

    await asyncio.gather(*[_one(eid) for eid in endpoint_ids])


async def test_endpoint(
    db: AsyncSession,
    endpoint_id: UUID,
    *,
    event: str = "test.ping",
) -> WebhookDelivery | None:
    endpoint = await db.get(WebhookEndpoint, endpoint_id)
    if endpoint is None:
        return None
    return await deliver(db, endpoint, event, {"message": "Test ping"})
