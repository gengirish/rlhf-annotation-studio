import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course import CourseModule, CourseSession
from app.models.task_pack import TaskPack
from app.models.work_session import WorkSession


class CourseService:
    @staticmethod
    async def get_overview(db: AsyncSession) -> list[CourseModule]:
        """Return all modules with their sessions, ordered by number."""
        result = await db.execute(
            select(CourseModule)
            .options(selectinload(CourseModule.sessions))
            .order_by(CourseModule.sort_order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_module(db: AsyncSession, number: int) -> CourseModule | None:
        """Get a single module with its sessions."""
        result = await db.execute(
            select(CourseModule)
            .where(CourseModule.number == number)
            .options(selectinload(CourseModule.sessions))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_session(db: AsyncSession, number: int) -> CourseSession | None:
        """Get a session with its module and linked task packs."""
        result = await db.execute(
            select(CourseSession)
            .where(CourseSession.number == number)
            .options(
                selectinload(CourseSession.module),
                selectinload(CourseSession.task_packs),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def compute_progress(db: AsyncSession, annotator_id: Any) -> dict[str, Any]:
        """Compute course progress for an annotator.

        A session is "completed" when all tasks in all linked packs
        have been annotated (status = "done" in the workspace).
        """
        modules = await CourseService.get_overview(db)

        # Get annotator's latest work session to check annotations
        ws_result = await db.execute(
            select(WorkSession)
            .where(WorkSession.annotator_id == annotator_id)
            .order_by(WorkSession.updated_at.desc())
            .limit(1)
        )
        work_session = ws_result.scalar_one_or_none()
        annotations: dict[str, Any] = {}
        if work_session and isinstance(work_session.annotations_json, dict):
            annotations = work_session.annotations_json

        module_progress: list[dict[str, Any]] = []
        total_completed = 0
        current_session: int | None = None

        for mod in modules:
            session_items: list[dict[str, Any]] = []
            completed_in_module = 0
            for sess in mod.sessions:
                # Load task packs for this session
                pack_result = await db.execute(
                    select(TaskPack).where(TaskPack.session_id == sess.id)
                )
                packs = list(pack_result.scalars().all())
                packs_total = len(packs)
                packs_completed = 0
                for pack in packs:
                    tasks = pack.tasks_json or []
                    if not tasks:
                        continue
                    all_done = all(
                        isinstance(annotations.get(str(t.get("id", ""))), dict)
                        and annotations.get(str(t.get("id", "")), {}).get("status") == "done"
                        for t in tasks
                        if isinstance(t, dict) and t.get("id")
                    )
                    if all_done and tasks:
                        packs_completed += 1

                sess_completed = packs_total > 0 and packs_completed == packs_total
                if sess_completed:
                    completed_in_module += 1
                    total_completed += 1
                elif current_session is None:
                    current_session = sess.number

                session_items.append(
                    {
                        "session_number": sess.number,
                        "session_title": sess.title,
                        "completed": sess_completed,
                        "packs_total": packs_total,
                        "packs_completed": packs_completed,
                    }
                )

            module_progress.append(
                {
                    "module_number": mod.number,
                    "module_title": mod.title,
                    "sessions": session_items,
                    "completed_sessions": completed_in_module,
                    "total_sessions": len(mod.sessions),
                }
            )

        total_sessions = sum(len(m.sessions) for m in modules)
        if current_session is None and total_completed < total_sessions:
            # Find first session
            for mod in modules:
                if mod.sessions:
                    current_session = mod.sessions[0].number
                    break

        return {
            "modules": module_progress,
            "total_sessions": total_sessions,
            "completed_sessions": total_completed,
            "current_session": current_session,
        }

    @staticmethod
    def parse_module_overview(md_text: str) -> dict[str, Any]:
        """Extract structured fields from a module overview markdown."""
        result: dict[str, Any] = {
            "title": "",
            "overview": "",
            "prerequisites": None,
            "estimated_time": "",
            "skills": [],
            "bridge_text": None,
        }

        lines = md_text.split("\n")
        current_section = ""
        section_lines: list[str] = []

        for line in lines:
            if line.startswith("# "):
                result["title"] = line.lstrip("# ").strip()
            elif line.startswith("## "):
                # Save previous section
                CourseService._save_module_section(result, current_section, section_lines)
                current_section = line.lstrip("## ").strip()
                section_lines = []
            else:
                section_lines.append(line)

        CourseService._save_module_section(result, current_section, section_lines)
        return result

    @staticmethod
    def _save_module_section(result: dict[str, Any], section: str, lines: list[str]) -> None:
        text = "\n".join(lines).strip()
        sec = section.lower()
        if "overview" in sec and "module" in sec:
            result["overview"] = text
        elif "prerequisite" in sec:
            result["prerequisites"] = text
        elif "estimated" in sec or "time" in sec:
            result["estimated_time"] = text
        elif "skill" in sec or "key skill" in sec:
            result["skills"] = [
                line.lstrip("- ").strip() for line in lines if line.strip().startswith("-")
            ]
        elif "bridge" in sec:
            result["bridge_text"] = text

    @staticmethod
    def parse_session_overview(md_text: str) -> dict[str, Any]:
        """Extract structured fields from a session overview markdown."""
        result: dict[str, Any] = {
            "title": "",
            "objectives": [],
            "duration": "90-120 minutes",
            "outline": [],
        }

        lines = md_text.split("\n")
        current_section = ""
        section_lines: list[str] = []

        for line in lines:
            if line.startswith("# "):
                result["title"] = line.lstrip("# ").strip()
            elif line.startswith("## "):
                CourseService._save_session_section(result, current_section, section_lines)
                current_section = line.lstrip("## ").strip()
                section_lines = []
            else:
                section_lines.append(line)

        CourseService._save_session_section(result, current_section, section_lines)
        return result

    @staticmethod
    def _save_session_section(result: dict[str, Any], section: str, lines: list[str]) -> None:
        text = "\n".join(lines).strip()
        sec = section.lower()
        if "learning objective" in sec:
            result["objectives"] = [
                line.lstrip("- ").strip() for line in lines if line.strip().startswith("-")
            ]
        elif "duration" in sec:
            match = re.search(r"(\d+[–-]\d+\s*minutes?)", text)
            if match:
                result["duration"] = match.group(1)
        elif "outline" in sec or "session outline" in sec:
            # Parse outline into sections
            current_part: dict[str, Any] | None = None
            parts: list[dict[str, Any]] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### "):
                    if current_part:
                        parts.append(current_part)
                    current_part = {
                        "title": stripped.lstrip("# ").strip(),
                        "items": [],
                    }
                elif stripped.startswith(("1.", "2.", "3.", "4.", "5.")) and current_part:
                    item = re.sub(r"^\d+\.\s*", "", stripped)
                    current_part["items"].append(item)
            if current_part:
                parts.append(current_part)
            result["outline"] = parts
