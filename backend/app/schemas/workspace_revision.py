import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkspaceRevisionRead(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    annotator_id: uuid.UUID
    revision_number: int
    annotations_snapshot: dict[str, Any]
    task_times_snapshot: dict[str, Any]
    created_at: datetime


class WorkspaceHistoryResponse(BaseModel):
    revisions: list[WorkspaceRevisionRead]
