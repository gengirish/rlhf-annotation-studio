from typing import Any

from pydantic import BaseModel, Field


class TaskValidationRequest(BaseModel):
    tasks: list[dict[str, Any]]
    strict_mode: bool = False


class TaskValidationIssue(BaseModel):
    row_index: int
    row_label: str
    message: str


class TaskValidationResponse(BaseModel):
    ok: bool
    strict_mode: bool
    total_tasks: int
    valid_tasks: int
    issues: list[TaskValidationIssue] = Field(default_factory=list)
