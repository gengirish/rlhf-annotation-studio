from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WorkSession, WorkspaceRevision
from app.schemas.session import WorkspacePutResponse, WorkspaceRead, WorkspaceUpdate
from app.services.annotation_validation_service import AnnotationValidationService


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

    async def put_workspace(self, session_id: UUID, user_id: UUID, body: WorkspaceUpdate) -> WorkspacePutResponse:
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

        tasks_for_validation = row.tasks_json
        annotations_for_validation = body.annotations if isinstance(body.annotations, dict) else {}

        count_result = await self.db.execute(
            select(func.count()).select_from(WorkspaceRevision).where(WorkspaceRevision.session_id == session_id)
        )
        prev_count = int(count_result.scalar_one() or 0)
        revision = WorkspaceRevision(
            session_id=session_id,
            annotator_id=user_id,
            revision_number=prev_count + 1,
            annotations_snapshot=dict(annotations_for_validation),
            task_times_snapshot=dict(body.task_times) if isinstance(body.task_times, dict) else {},
        )
        self.db.add(revision)

        await self.db.commit()

        warnings = AnnotationValidationService().validate(tasks_for_validation, annotations_for_validation)

        return WorkspacePutResponse(ok=True, annotation_warnings=warnings)

    async def list_workspace_history(
        self,
        session_id: UUID,
        user_id: UUID,
        limit: int = 20,
    ) -> list[WorkspaceRevision]:
        row = await self.db.get(WorkSession, session_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        if row.annotator_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")

        result = await self.db.execute(
            select(WorkspaceRevision)
            .where(WorkspaceRevision.session_id == session_id)
            .order_by(WorkspaceRevision.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
