from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from app.schemas.task_pack import TaskPackSummary


class CourseSessionBrief(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    duration: str

    model_config = {"from_attributes": True}


class CourseModuleRead(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    overview_md: str
    prerequisites: str | None
    estimated_time: str
    skills_json: list[str]
    bridge_text: str | None
    session_count: int
    sessions: list[CourseSessionBrief]

    model_config = {"from_attributes": True}


class CourseModuleBrief(BaseModel):
    id: uuid.UUID
    number: int
    title: str
    estimated_time: str
    session_count: int

    model_config = {"from_attributes": True}


class CourseSessionRead(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    number: int
    title: str
    overview_md: str
    rubric_md: str | None
    questions_md: str | None
    exercises_md: str | None
    ai_tasks_md: str | None
    resources_md: str | None
    duration: str
    objectives_json: list[str]
    outline_json: list[dict[str, Any]]
    task_packs: list[TaskPackSummary]
    module: CourseModuleBrief

    model_config = {"from_attributes": True}


class SessionProgressItem(BaseModel):
    session_number: int
    session_title: str
    completed: bool
    packs_total: int
    packs_completed: int


class ModuleProgressItem(BaseModel):
    module_number: int
    module_title: str
    sessions: list[SessionProgressItem]
    completed_sessions: int
    total_sessions: int


class CourseProgressResponse(BaseModel):
    modules: list[ModuleProgressItem]
    total_sessions: int
    completed_sessions: int
    current_session: int | None


class CourseOverviewResponse(BaseModel):
    modules: list[CourseModuleRead]
    total_modules: int
    total_sessions: int
