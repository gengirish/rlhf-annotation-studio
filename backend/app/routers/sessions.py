from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, WorkSession
from app.schemas.annotator import AnnotatorRead
from app.schemas.session import (
    BootstrapRequest,
    BootstrapResponse,
    WorkspacePutResponse,
    WorkspaceRead,
    WorkspaceUpdate,
)
from app.schemas.workspace_revision import WorkspaceHistoryResponse, WorkspaceRevisionRead
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "/bootstrap",
    response_model=BootstrapResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def bootstrap(
    body: BootstrapRequest,
    db: AsyncSession = Depends(get_db),
    _user: Annotator = Depends(get_current_user),
) -> BootstrapResponse:
    """Create annotator row + empty work session; browser stores `session_id` for sync."""
    annotator = Annotator(
        name=body.annotator.name,
        email=str(body.annotator.email),
        phone=body.annotator.phone,
    )
    db.add(annotator)
    await db.flush()

    session = WorkSession(
        annotator_id=annotator.id,
        tasks_json=None,
        annotations_json={},
        task_times_json={},
        active_pack_file=None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(annotator)
    await db.refresh(session)

    return BootstrapResponse(
        annotator=AnnotatorRead.model_validate(annotator),
        session_id=session.id,
    )


@router.get("/{session_id}/workspace", response_model=WorkspaceRead)
async def get_workspace(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WorkspaceRead:
    return await WorkspaceService(db).get_workspace(session_id=session_id, user_id=current_user.id)


@router.put("/{session_id}/workspace", response_model=WorkspacePutResponse)
async def put_workspace(
    session_id: UUID,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WorkspacePutResponse:
    """Replace workspace JSON (tasks, annotations, timings) from the annotation UI."""
    return await WorkspaceService(db).put_workspace(
        session_id=session_id,
        user_id=current_user.id,
        body=body,
    )


@router.get("/{session_id}/workspace/history", response_model=WorkspaceHistoryResponse)
async def get_workspace_history(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> WorkspaceHistoryResponse:
    """Last 20 saved workspace snapshots (annotations + task times) for this session."""
    rows = await WorkspaceService(db).list_workspace_history(session_id=session_id, user_id=current_user.id)
    return WorkspaceHistoryResponse(revisions=[WorkspaceRevisionRead.model_validate(r) for r in rows])
