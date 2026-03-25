from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkSession
from app.schemas.session import WorkspaceRead, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workspace(self, session_id: UUID, user_id: UUID) -> WorkspaceRead:
        row = await self.db.get(WorkSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if row.annotator_id != user_id:
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

    async def put_workspace(self, session_id: UUID, user_id: UUID, body: WorkspaceUpdate) -> dict[str, bool]:
        row = await self.db.get(WorkSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if row.annotator_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

        if body.tasks is not None:
            row.tasks_json = body.tasks
        row.annotations_json = body.annotations
        row.task_times_json = body.task_times
        row.active_pack_file = body.active_pack_file

        await self.db.commit()
        return {"ok": True}

