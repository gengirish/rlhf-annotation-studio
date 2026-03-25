from fastapi import APIRouter

from app.schemas.task_validation import TaskValidationRequest, TaskValidationResponse
from app.services.task_validation_service import TaskValidationService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/validate", response_model=TaskValidationResponse)
async def validate_tasks(body: TaskValidationRequest) -> TaskValidationResponse:
    issues, invalid_rows = TaskValidationService().validate_tasks(body.tasks)
    valid_tasks = len(body.tasks) - len(invalid_rows)
    ok = not issues if body.strict_mode else valid_tasks > 0
    return TaskValidationResponse(
        ok=ok,
        strict_mode=body.strict_mode,
        total_tasks=len(body.tasks),
        valid_tasks=max(valid_tasks, 0),
        issues=issues,
    )
