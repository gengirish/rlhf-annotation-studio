"""Seed course_modules and course_sessions from external code-reviewer-course markdown.

Usage (from backend/):
    python seed_course_content.py
    python seed_course_content.py --content-dir "C:/path/to/code-reviewer-course/content"
    python seed_course_content.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(__file__))

from app.db import AsyncSessionLocal  # noqa: E402
from app.models.course import CourseModule, CourseSession  # noqa: E402
from app.models.task_pack import TaskPack  # noqa: E402
from app.services.course_service import CourseService  # noqa: E402

_script_dir = Path(__file__).resolve().parent

SESSIONS: dict[str, dict[str, str]] = {
    "01": {"module": "module-1", "title": "Introduction to AI Code Reviewing"},
    "02": {"module": "module-1", "title": "Reading and Understanding Code"},
    "03": {"module": "module-2", "title": "Python Code Evaluation"},
    "04": {"module": "module-2", "title": "Java Code Evaluation"},
    "05": {"module": "module-2", "title": "JavaScript / TypeScript Evaluation"},
    "06": {"module": "module-2", "title": "C#, C++ or Language of Choice"},
    "07": {"module": "module-3", "title": "Debugging Fundamentals"},
    "08": {"module": "module-3", "title": "Code Correction Techniques"},
    "09": {"module": "module-3", "title": "Test Cases & Edge Case Analysis"},
    "10": {"module": "module-4", "title": "Code Style Guidelines"},
    "11": {"module": "module-4", "title": "Clean Code Principles"},
    "12": {"module": "module-4", "title": "Performance & Complexity Review"},
    "13": {"module": "module-5", "title": "Ranking AI-Generated Code"},
    "14": {"module": "module-5", "title": "Scoring Code Against a Rubric"},
    "15": {"module": "module-5", "title": "Fixing AI Mistakes"},
    "16": {"module": "module-6", "title": "Multi-Language Evaluation"},
    "17": {"module": "module-6", "title": "Identifying Security Risks"},
    "18": {"module": "module-6", "title": "Documentation & Explanation Writing"},
    "19": {"module": "module-7", "title": "Platforms Used by AI Review Companies"},
    "20": {"module": "module-7", "title": "GitHub & PR Code Review Basics"},
    "21": {"module": "module-8", "title": "Full AI Code Review Project — Part 1"},
    "22": {"module": "module-8", "title": "Full AI Code Review Project — Part 2"},
    "23": {"module": "module-8", "title": "Mock RLHF Coding Task"},
    "24": {"module": "module-8", "title": "Final Practical Test"},
    "25": {"module": "module-9", "title": "Resume, Project Portfolio & Job Search Strategy"},
}

MODULE_TITLES: dict[int, str] = {
    1: "Fundamentals of Code Reading & Analysis",
    2: "Language-Specific Code Evaluation",
    3: "Debugging & Code Correction",
    4: "Code Quality & Best Practices",
    5: "AI-Specific Code Review Work",
    6: "Advanced Review Topics",
    7: "Industry Tools & Platforms",
    8: "Capstone Projects & Assessment",
    9: "Career Preparation",
}

SESSION_SLUG_RE = re.compile(r"session-(\d+)", re.IGNORECASE)
MODULE_SLUG_RE = re.compile(r"module-(\d+)", re.IGNORECASE)


def _read_file(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _default_content_dir_candidates() -> list[Path]:
    return [
        _script_dir.parent / "code-reviewer-course" / "content",
        _script_dir.parent.parent / "code-reviewer-course" / "content",
    ]


def _resolve_content_dir(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.is_dir() else None
    for candidate in _default_content_dir_candidates():
        if candidate.is_dir():
            return candidate
    return None


def _module_number_from_slug(module_slug: str) -> int:
    return int(module_slug.removeprefix("module-"))


def _session_counts_by_module() -> dict[int, int]:
    counts: dict[int, int] = {}
    for meta in SESSIONS.values():
        n = _module_number_from_slug(meta["module"])
        counts[n] = counts.get(n, 0) + 1
    return counts


def _sort_order_in_module(session_key: str) -> int:
    module_slug = SESSIONS[session_key]["module"]
    same_module = sorted(
        (k for k, v in SESSIONS.items() if v["module"] == module_slug),
        key=lambda k: int(k),
    )
    return same_module.index(session_key) + 1


def _parse_slug_task_pack(slug: str) -> tuple[int | None, int | None]:
    """Return (module_number, session_number) from course-content slugs, if parseable."""
    mod_m = MODULE_SLUG_RE.search(slug)
    sess_m = SESSION_SLUG_RE.search(slug)
    mod_num = int(mod_m.group(1)) if mod_m else None
    sess_num = int(sess_m.group(1)) if sess_m else None
    return mod_num, sess_num


async def seed(session: Any, content_dir: Path, dry_run: bool = False) -> None:
    session_counts = _session_counts_by_module()

    if dry_run:
        print(f"Dry run: would ingest course content from {content_dir}")
        for mod_num in range(1, 10):
            overview_path = content_dir / f"module-{mod_num}" / f"module-{mod_num}-overview.md"
            raw = _read_file(overview_path)
            if raw is None:
                print(f"  WOULD SKIP  module {mod_num}: missing {overview_path.name}")
            else:
                parsed = CourseService.parse_module_overview(raw)
                sc = session_counts.get(mod_num, 0)
                print(
                    f"  WOULD UPSERT  CourseModule number={mod_num} "
                    f"title={MODULE_TITLES.get(mod_num, parsed.get('title', ''))!r} "
                    f"session_count={sc} <- {overview_path.relative_to(content_dir)}"
                )

        for sess_key in sorted(SESSIONS.keys(), key=int):
            meta = SESSIONS[sess_key]
            mod_slug = meta["module"]
            sess_dir = content_dir / mod_slug / f"session-{sess_key}"
            overview_path = sess_dir / f"session-{sess_key}-overview.md"
            overview = _read_file(overview_path)
            if overview is None:
                print(f"  WOULD UPSERT  session {int(sess_key)} (no overview file): {sess_dir}")
            else:
                po = CourseService.parse_session_overview(overview)
                print(
                    f"  WOULD UPSERT  CourseSession number={int(sess_key)} "
                    f"module={mod_slug} title={meta['title']!r} "
                    f"objectives={len(po.get('objectives', []))} "
                    f"outline_parts={len(po.get('outline', []))} "
                    f"duration={po.get('duration')!r} <- {overview_path.relative_to(content_dir)}"
                )
            for suffix, label in [
                ("rubric", "rubric_md"),
                ("questions", "questions_md"),
                ("debugging-exercises", "exercises_md"),
                ("ai-comparison-tasks", "ai_tasks_md"),
                ("resources", "resources_md"),
            ]:
                p = sess_dir / f"session-{sess_key}-{suffix}.md"
                if p.exists():
                    print(f"      include  {label} <- {p.name}")
                else:
                    print(f"      (missing) {label} <- {p.name}")

        print(
            "  WOULD LINK  task packs with slug starting"
            " 'course-content-module-' by session number"
        )
        print("Dry run complete (no DB changes committed).")
        return

    modules_by_number: dict[int, CourseModule] = {}

    for mod_num in range(1, 10):
        overview_path = content_dir / f"module-{mod_num}" / f"module-{mod_num}-overview.md"
        raw = _read_file(overview_path)
        if raw is None:
            print(f"  SKIP  module {mod_num}: missing {overview_path}")
            continue

        parsed = CourseService.parse_module_overview(raw)
        title = MODULE_TITLES.get(mod_num, parsed.get("title") or f"Module {mod_num}")
        session_count = session_counts.get(mod_num, 0)

        result = await session.execute(select(CourseModule).where(CourseModule.number == mod_num))
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = title
            existing.overview_md = raw
            existing.prerequisites = parsed.get("prerequisites")
            existing.estimated_time = parsed.get("estimated_time") or ""
            existing.skills_json = parsed.get("skills") or []
            existing.bridge_text = parsed.get("bridge_text")
            existing.session_count = session_count
            existing.sort_order = mod_num
            modules_by_number[mod_num] = existing
            print(f"  UPDATE  CourseModule {mod_num} ({title!r}) session_count={session_count}")
        else:
            row = CourseModule(
                number=mod_num,
                title=title,
                overview_md=raw,
                prerequisites=parsed.get("prerequisites"),
                estimated_time=parsed.get("estimated_time") or "",
                skills_json=parsed.get("skills") or [],
                bridge_text=parsed.get("bridge_text"),
                session_count=session_count,
                sort_order=mod_num,
            )
            session.add(row)
            modules_by_number[mod_num] = row
            print(f"  INSERT  CourseModule {mod_num} ({title!r}) session_count={session_count}")

    await session.flush()

    for sess_key in sorted(SESSIONS.keys(), key=int):
        meta = SESSIONS[sess_key]
        mod_slug = meta["module"]
        mod_num = _module_number_from_slug(mod_slug)
        module_row = modules_by_number.get(mod_num)
        if module_row is None:
            print(
                f"  SKIP  session {sess_key}: module {mod_num} not loaded "
                f"(missing module overview?)"
            )
            continue

        sess_dir = content_dir / mod_slug / f"session-{sess_key}"
        overview = _read_file(sess_dir / f"session-{sess_key}-overview.md") or ""
        parsed = CourseService.parse_session_overview(overview) if overview else {}
        title = meta["title"]
        duration = parsed.get("duration") or "90-120 minutes"
        objectives = parsed.get("objectives") or []
        outline = parsed.get("outline") or []
        sort_order = _sort_order_in_module(sess_key)
        session_num = int(sess_key)

        rubric_md = _read_file(sess_dir / f"session-{sess_key}-rubric.md")
        questions_md = _read_file(sess_dir / f"session-{sess_key}-questions.md")
        exercises_md = _read_file(sess_dir / f"session-{sess_key}-debugging-exercises.md")
        ai_tasks_md = _read_file(sess_dir / f"session-{sess_key}-ai-comparison-tasks.md")
        resources_md = _read_file(sess_dir / f"session-{sess_key}-resources.md")

        res = await session.execute(
            select(CourseSession).where(CourseSession.number == session_num)
        )
        existing_sess = res.scalar_one_or_none()

        if existing_sess:
            existing_sess.module_id = module_row.id
            existing_sess.title = title
            existing_sess.overview_md = overview
            existing_sess.rubric_md = rubric_md
            existing_sess.questions_md = questions_md
            existing_sess.exercises_md = exercises_md
            existing_sess.ai_tasks_md = ai_tasks_md
            existing_sess.resources_md = resources_md
            existing_sess.duration = duration
            existing_sess.objectives_json = objectives
            existing_sess.outline_json = outline
            existing_sess.sort_order = sort_order
            print(f"  UPDATE  CourseSession {session_num:02d} ({title!r}) module={mod_num}")
        else:
            session.add(
                CourseSession(
                    module_id=module_row.id,
                    number=session_num,
                    title=title,
                    overview_md=overview,
                    rubric_md=rubric_md,
                    questions_md=questions_md,
                    exercises_md=exercises_md,
                    ai_tasks_md=ai_tasks_md,
                    resources_md=resources_md,
                    duration=duration,
                    objectives_json=objectives,
                    outline_json=outline,
                    sort_order=sort_order,
                )
            )
            print(f"  INSERT  CourseSession {session_num:02d} ({title!r}) module={mod_num}")

    await session.flush()

    tp_result = await session.execute(
        select(TaskPack).where(TaskPack.slug.startswith("course-content-module-"))
    )
    packs = list(tp_result.scalars().all())
    if not packs:
        print("  (no task packs with slug prefix 'course-content-module-')")
    else:
        for pack in packs:
            mod_from_slug, sess_from_slug = _parse_slug_task_pack(pack.slug)
            if sess_from_slug is None:
                print(f"  SKIP LINK  {pack.slug!r} (could not parse session-NN from slug)")
                continue
            sess_res = await session.execute(
                select(CourseSession).where(CourseSession.number == sess_from_slug)
            )
            course_session = sess_res.scalar_one_or_none()
            if course_session is None:
                print(
                    f"  SKIP LINK  {pack.slug!r} -> no CourseSession with number={sess_from_slug}"
                )
                continue
            if mod_from_slug is not None:
                mod_num = _module_number_from_slug(SESSIONS[f"{sess_from_slug:02d}"]["module"])
                if mod_from_slug != mod_num:
                    print(
                        f"  WARN LINK  {pack.slug!r}: slug module {mod_from_slug} != "
                        f"expected module {mod_num} for session {sess_from_slug}"
                    )
            if pack.session_id != course_session.id:
                pack.session_id = course_session.id
                print(f"  LINK  {pack.slug} -> CourseSession number={sess_from_slug}")
            else:
                print(f"  OK    {pack.slug} already linked to session {sess_from_slug}")

    await session.commit()
    print("Done.")


async def main(content_dir: Path | None, dry_run: bool) -> None:
    resolved = _resolve_content_dir(content_dir)
    if resolved is None:
        tried = (
            [str(content_dir)]
            if content_dir is not None
            else [str(p) for p in _default_content_dir_candidates()]
        )
        print("Course content directory not found (non-fatal). Tried:")
        for t in tried:
            print(f"  {t}")
        print("Skipping course content seeding.")
        return

    print(f"Using content directory: {resolved}")

    async with AsyncSessionLocal() as session:
        await seed(session, resolved, dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed course modules/sessions from code-reviewer-course markdown"
    )
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=None,
        help=(
            "Path to code-reviewer-course/content"
            " (default: ../ or ../../ code-reviewer-course/content)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without committing DB changes",
    )
    args = parser.parse_args()
    asyncio.run(main(args.content_dir, dry_run=args.dry_run))
