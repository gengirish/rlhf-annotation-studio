from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import bcrypt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models.annotator import Annotator

security = HTTPBearer(auto_error=False)
inference_security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_annotator_from_bearer_token(token: str, db: AsyncSession) -> Annotator:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        user_id = UUID(sub)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None

    result = await db.execute(select(Annotator).where(Annotator.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Annotator:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await get_annotator_from_bearer_token(credentials.credentials, db)


ROLE_ADMIN = "admin"
ROLE_REVIEWER = "reviewer"
ROLE_ANNOTATOR = "annotator"
VALID_ROLES = {ROLE_ADMIN, ROLE_REVIEWER, ROLE_ANNOTATOR}


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that checks the current user has one of the allowed roles."""
    async def _check(current_user: Annotator = Depends(get_current_user)) -> Annotator:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not authorized. Requires: {', '.join(allowed_roles)}",
            )
        return current_user
    return _check


require_admin = require_role(ROLE_ADMIN)
require_reviewer_or_admin = require_role(ROLE_ADMIN, ROLE_REVIEWER)


async def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Annotator:
    """Authenticate via Bearer token OR X-API-Key header."""
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

    from app.models.api_key import APIKey
    from app.services.api_key_service import is_expired, verify_key

    raw = x_api_key.strip()
    if len(raw) < 8:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    prefix = raw[:8]
    result = await db.execute(
        select(APIKey).where(APIKey.key_prefix == prefix).where(APIKey.is_active.is_(True))
    )
    candidates = result.scalars().all()

    matched: "APIKey | None" = None
    for candidate in candidates:
        if verify_key(raw, candidate.key_hash):
            matched = candidate
            break

    if matched is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if is_expired(matched):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    from datetime import UTC as _utc
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(APIKey).where(APIKey.id == matched.id).values(last_used_at=datetime.now(_utc))
    )
    await db.commit()

    user = await db.get(Annotator, matched.annotator_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_inference_caller(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(inference_security),
    ],
    db: AsyncSession = Depends(get_db),
) -> None:
    if not settings.inference_require_auth:
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for inference",
        )
    await get_annotator_from_bearer_token(credentials.credentials, db)
