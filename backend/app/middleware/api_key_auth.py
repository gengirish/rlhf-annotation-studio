from datetime import UTC, datetime

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_annotator_from_bearer_token, security
from app.db import get_db
from app.models.annotator import Annotator
from app.models.api_key import APIKey
from app.services.api_key_service import is_expired, verify_key


async def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Annotator:
    if (
        credentials is not None
        and credentials.scheme.lower() == "bearer"
        and credentials.credentials
    ):
        return await get_annotator_from_bearer_token(credentials.credentials, db)

    if x_api_key is None or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    raw = x_api_key.strip()
    if len(raw) < 8:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    prefix = raw[:8]
    result = await db.execute(
        select(APIKey).where(APIKey.key_prefix == prefix).where(APIKey.is_active.is_(True))
    )
    candidates = result.scalars().all()

    matched: APIKey | None = None
    for candidate in candidates:
        if verify_key(raw, candidate.key_hash):
            matched = candidate
            break

    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    if is_expired(matched):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key expired",
        )

    await db.execute(
        update(APIKey)
        .where(APIKey.id == matched.id)
        .values(last_used_at=datetime.now(UTC))
    )
    await db.commit()

    user = await db.get(Annotator, matched.annotator_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
