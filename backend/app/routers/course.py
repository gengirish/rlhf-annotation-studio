from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models import Annotator
from app.schemas.course import (
    CourseModuleRead,
    CourseOverviewResponse,
    CourseProgressResponse,
    CourseSessionRead,
)
from app.services.course_service import CourseService

router = APIRouter(prefix="/course", tags=["course"])


@router.get("/overview", response_model=CourseOverviewResponse)
async def get_curriculum_overview(
    db: AsyncSession = Depends(get_db),
) -> CourseOverviewResponse:
    """Full curriculum tree — public endpoint."""
    modules = await CourseService.get_overview(db)
    module_reads = [CourseModuleRead.model_validate(m) for m in modules]
    return CourseOverviewResponse(
        modules=module_reads,
        total_modules=len(modules),
        total_sessions=sum(m.session_count for m in modules),
    )


@router.get("/modules", response_model=list[CourseModuleRead])
async def list_modules(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> list[CourseModuleRead]:
    modules = await CourseService.get_overview(db)
    return [CourseModuleRead.model_validate(m) for m in modules]


@router.get("/modules/{number}", response_model=CourseModuleRead)
async def get_module(
    number: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> CourseModuleRead:
    mod = await CourseService.get_module(db, number)
    if mod is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {number} not found",
        )
    return CourseModuleRead.model_validate(mod)


@router.get("/sessions/{number}", response_model=CourseSessionRead)
async def get_session(
    number: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> CourseSessionRead:
    sess = await CourseService.get_session(db, number)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {number} not found",
        )
    return CourseSessionRead.model_validate(sess)


@router.get("/sessions/{number}/rubric")
async def get_session_rubric(
    number: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> dict[str, str | None]:
    sess = await CourseService.get_session(db, number)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {number} not found",
        )
    return {"rubric_md": sess.rubric_md}


@router.get("/sessions/{number}/questions")
async def get_session_questions(
    number: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> dict[str, str | None]:
    sess = await CourseService.get_session(db, number)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {number} not found",
        )
    return {"questions_md": sess.questions_md}


@router.get("/sessions/{number}/resources")
async def get_session_resources(
    number: int,
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> dict[str, str | None]:
    sess = await CourseService.get_session(db, number)
    if sess is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {number} not found",
        )
    return {"resources_md": sess.resources_md}


@router.get("/progress", response_model=CourseProgressResponse)
async def get_progress(
    db: AsyncSession = Depends(get_db),
    current_user: Annotator = Depends(get_current_user),
) -> CourseProgressResponse:
    data = await CourseService.compute_progress(db, current_user.id)
    return CourseProgressResponse(**data)
