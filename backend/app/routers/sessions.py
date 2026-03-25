from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator, WorkSession
from app.schemas.annotator import AnnotatorRead
from app.schemas.session import BootstrapRequest, BootstrapResponse, WorkspaceRead, WorkspaceUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/bootstrap", response_model=BootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(body: BootstrapRequest, db: AsyncSession = Depends(get_db)) -> BootstrapResponse:
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
    row = await db.get(WorkSession, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if row.annotator_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return WorkspaceRead(
        session_id=row.id,
        annotator_id=row.annotator_id,
        tasks=row.tasks_json,
        annotations=row.annotations_json or {},
        task_times=row.task_times_json or {},
        active_pack_file=row.active_pack_file,
        updated_at=row.updated_at,
    )


@router.put("/{session_id}/workspace")
async def put_workspace(
    session_id: UUID,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> dict[str, bool]:
    """Replace workspace JSON (tasks, annotations, timings) from the annotation UI."""
    row = await db.get(WorkSession, session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    if row.annotator_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

    if body.tasks is not None:
        row.tasks_json = body.tasks
    row.annotations_json = body.annotations
    row.task_times_json = body.task_times
    row.active_pack_file = body.active_pack_file

    await db.commit()
    return {"ok": True}
