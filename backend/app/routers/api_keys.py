from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.annotator import Annotator
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyRead, APIKeyUpdate
from app.services.api_key_service import generate_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=APIKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> APIKeyCreated:
    raw_key, key_hash, key_prefix = generate_key()
    expires_at: datetime | None = None
    if body.expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=body.expires_in_days)

    row = APIKey(
        annotator_id=current_user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=list(body.scopes),
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    base = APIKeyRead.model_validate(row)
    return APIKeyCreated.model_validate({**base.model_dump(), "key": raw_key})


@router.get("", response_model=list[APIKeyRead])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[APIKeyRead]:
    result = await db.execute(
        select(APIKey)
        .where(APIKey.annotator_id == current_user.id)
        .order_by(APIKey.created_at.desc())
    )
    rows = result.scalars().all()
    return [APIKeyRead.model_validate(r) for r in rows]


@router.patch("/{key_id}", response_model=APIKeyRead)
async def update_api_key(
    key_id: UUID,
    body: APIKeyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> APIKeyRead:
    row = await db.get(APIKey, key_id)
    if row is None or row.annotator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    if body.name is None and body.scopes is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields to update",
        )

    if body.name is not None:
        row.name = body.name
    if body.scopes is not None:
        row.scopes = list(body.scopes)
    if body.is_active is not None:
        row.is_active = body.is_active

    await db.commit()
    await db.refresh(row)
    return APIKeyRead.model_validate(row)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> None:
    row = await db.get(APIKey, key_id)
    if row is None or row.annotator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await db.delete(row)
    await db.commit()
