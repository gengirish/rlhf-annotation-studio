from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.annotator import Annotator
from app.models.webhook import WebhookDelivery, WebhookEndpoint
from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryRead,
    WebhookRead,
    WebhookTest,
    WebhookUpdate,
)
from app.services.webhook_service import register_endpoint, test_endpoint

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _get_owned_endpoint(
    db: AsyncSession,
    current_user: Annotator,
    webhook_id: UUID,
) -> WebhookEndpoint:
    row = await db.get(WebhookEndpoint, webhook_id)
    if row is None or row.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return row


@router.post("", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WebhookRead:
    row = await register_endpoint(db, current_user, body)
    return WebhookRead.model_validate(row)


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[WebhookRead]:
    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.owner_id == current_user.id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    rows = result.scalars().all()
    return [WebhookRead.model_validate(r) for r in rows]


@router.get("/{webhook_id}", response_model=WebhookRead)
async def get_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WebhookRead:
    row = await _get_owned_endpoint(db, current_user, webhook_id)
    return WebhookRead.model_validate(row)


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDeliveryRead])
async def list_webhook_deliveries(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[WebhookDeliveryRead]:
    await _get_owned_endpoint(db, current_user, webhook_id)
    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = result.scalars().all()
    return [WebhookDeliveryRead.model_validate(r) for r in rows]


@router.post("/{webhook_id}/test", response_model=WebhookDeliveryRead)
async def test_webhook(
    webhook_id: UUID,
    body: WebhookTest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WebhookDeliveryRead:
    await _get_owned_endpoint(db, current_user, webhook_id)
    payload = body if body is not None else WebhookTest()
    delivery = await test_endpoint(db, webhook_id, event=payload.event)
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return WebhookDeliveryRead.model_validate(delivery)


@router.patch("/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WebhookRead:
    row = await _get_owned_endpoint(db, current_user, webhook_id)
    if body.url is not None:
        row.url = body.url.strip()
    if body.events is not None:
        row.events = list(body.events)
    if body.is_active is not None:
        row.is_active = body.is_active
    await db.commit()
    await db.refresh(row)
    return WebhookRead.model_validate(row)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> None:
    row = await _get_owned_endpoint(db, current_user, webhook_id)
    await db.delete(row)
    await db.commit()
