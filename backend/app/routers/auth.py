import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import VALID_ROLES, create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.annotator import Annotator
from app.models.work_session import WorkSession
from app.schemas.annotator import AnnotatorRead

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    phone: str | None = None
    role: str = Field(default="annotator", pattern="^(reviewer|annotator)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    annotator: AnnotatorRead
    session_id: uuid.UUID


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    existing = await db.execute(select(Annotator).where(Annotator.email == str(body.email)))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    annotator = Annotator(
        name=body.name,
        email=str(body.email),
        password_hash=hash_password(body.password),
        phone=body.phone,
        role=body.role,
    )
    db.add(annotator)
    await db.flush()

    work_session = WorkSession(
        annotator_id=annotator.id,
        tasks_json=None,
        annotations_json={},
        task_times_json={},
        active_pack_file=None,
    )
    db.add(work_session)
    await db.commit()
    await db.refresh(annotator)
    await db.refresh(work_session)

    token = create_access_token({"sub": str(annotator.id)})
    return AuthResponse(
        token=token,
        annotator=AnnotatorRead.model_validate(annotator),
        session_id=work_session.id,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    result = await db.execute(select(Annotator).where(Annotator.email == str(body.email)))
    annotator = result.scalar_one_or_none()
    if annotator is None or not annotator.password_hash or not verify_password(
        body.password, annotator.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    ws_result = await db.execute(
        select(WorkSession)
        .where(WorkSession.annotator_id == annotator.id)
        .order_by(WorkSession.updated_at.desc())
        .limit(1)
    )
    work_session = ws_result.scalar_one_or_none()
    if work_session is None:
        work_session = WorkSession(
            annotator_id=annotator.id,
            tasks_json=None,
            annotations_json={},
            task_times_json={},
            active_pack_file=None,
        )
        db.add(work_session)

    await db.commit()
    await db.refresh(annotator)
    await db.refresh(work_session)

    token = create_access_token({"sub": str(annotator.id)})
    return AuthResponse(
        token=token,
        annotator=AnnotatorRead.model_validate(annotator),
        session_id=work_session.id,
    )
