"""Seed task_packs table from JSON files in backend/tasks (recursive).

Usage (from backend/):
    python seed_task_packs.py
    python seed_task_packs.py --dry-run
"""

import asyncio
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(__file__))

from app.db import AsyncSessionLocal  # noqa: E402
from app.models.task_pack import TaskPack  # noqa: E402

_script_dir = Path(__file__).resolve().parent
TASKS_DIR = _script_dir / "tasks" if (_script_dir / "tasks").is_dir() else _script_dir.parent / "tasks"

ROOT_OVERRIDES: dict[str, dict[str, str]] = {
    "debugging-exercises-python.json": {
        "slug": "debugging-exercises-python",
        "name": "Python Debugging",
        "description": "9 debugging-focused comparison tasks covering mutable defaults, closures, generators, and scoping",
        "language": "python",
    },
    "debugging-exercises-java.json": {
        "slug": "debugging-exercises-java",
        "name": "Java Debugging",
        "description": "9 Java debugging tasks with common pitfalls like == vs .equals(), ConcurrentModification, BigDecimal",
        "language": "java",
    },
    "debugging-exercises.json": {
        "slug": "debugging-exercises",
        "name": "Debugging Exercises (Module 2)",
        "description": "Debugging comparison tasks from the AI Code Reviewer course Module 2 Session 3",
        "language": "java",
    },
    "code-review-comparisons.json": {
        "slug": "code-review-comparisons",
        "name": "Code Review Comparisons",
        "description": "4 code review quality tasks — SQL injection, React optimization, API design, git commit messages",
        "language": "multi",
    },
    "safety-alignment.json": {
        "slug": "safety-alignment",
        "name": "Safety and Alignment",
        "description": "3 safety-oriented evaluation tasks — medical safety, refusal quality, bias detection",
        "language": "general",
    },
    "hf-live-demo.json": {
        "slug": "hf-live-demo",
        "name": "Hugging Face Live Demo",
        "description": "Live model comparison tasks — edit prompts, select 2 models, compare responses side by side",
        "language": "python",
    },
    "m2-s05-javascript-debugging.json": {
        "slug": "m2-s05-javascript-debugging",
        "name": "Session 05: JavaScript Debugging",
        "description": "9 JavaScript debugging tasks — type coercion, async/await, closures, this binding, truthy/falsy, Promise handling, strict equality",
        "language": "javascript",
    },
    "m2-s06-csharp-cpp-debugging.json": {
        "slug": "m2-s06-csharp-cpp-debugging",
        "name": "Session 06: C# and C++ Debugging",
        "description": "3 debugging tasks — IDisposable resource leaks, async void, LINQ deferred execution, C++ memory leaks and RAII",
        "language": "csharp-cpp",
    },
    "m3-s07-cross-language-debugging.json": {
        "slug": "m3-s07-cross-language-debugging",
        "name": "Session 07: Cross-Language Debugging",
        "description": "7 foundational debugging tasks — off-by-one, null reference, infinite loops, type mismatch, uninitialized variables, stack overflow, stack trace reading",
        "language": "multi",
    },
}


def _slugify(text: str) -> str:
    text = text.strip().lower().replace("\\", "/")
    text = text.replace(".json", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def _titleize(stem: str) -> str:
    parts = re.split(r"[-_]+", stem)
    return " ".join(p.capitalize() if not p.isdigit() else p for p in parts if p)


def _infer_language(name: str) -> str:
    n = name.lower()
    if "python" in n:
        return "python"
    if "java" in n and "javascript" not in n:
        return "java"
    if "javascript" in n or "typescript" in n:
        return "javascript"
    if "csharp" in n or "cpp" in n:
        return "csharp-cpp"
    if "safety" in n:
        return "general"
    if "review" in n:
        return "multi"
    return "multi"


def discover_pack_meta() -> list[dict[str, Any]]:
    metas: list[dict[str, Any]] = []
    for path in sorted(TASKS_DIR.rglob("*.json")):
        rel = path.relative_to(TASKS_DIR).as_posix()
        stem = path.stem
        root_override = ROOT_OVERRIDES.get(path.name) if path.parent == TASKS_DIR else None
        slug = root_override["slug"] if root_override else _slugify(rel)
        name = root_override["name"] if root_override else _titleize(stem)
        language = root_override["language"] if root_override else _infer_language(rel)
        description = (
            root_override["description"]
            if root_override
            else f"Auto-imported task pack from {rel}"
        )
        metas.append(
            {
                "path": path,
                "rel": rel,
                "slug": slug,
                "name": name,
                "description": description,
                "language": language,
            }
        )
    return metas


async def seed(session: AsyncSession, dry_run: bool = False) -> None:
    metas = discover_pack_meta()
    if not metas:
        print(f"No JSON files found under {TASKS_DIR}")
        return

    print(f"Discovered {len(metas)} task pack files in {TASKS_DIR}")

    if dry_run:
        for meta in metas:
            path = meta["path"]
            rel = meta["rel"]
            try:
                tasks = json.loads(path.read_text(encoding="utf-8"))
                task_count = len(tasks) if isinstance(tasks, list) else "invalid"
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP  {rel} (read error: {exc})")
                continue
            print(
                f"  WOULD UPSERT  {meta['slug']} ({task_count} tasks) <- {rel} "
                f"[{meta['language']}]"
            )
        print("Dry run complete (no DB connection, no changes committed).")
        return

    for meta in metas:
        path = meta["path"]
        rel = meta["rel"]
        if not path.exists():
            print(f"  SKIP  {rel} (file not found at {path})")
            continue

        tasks = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(tasks, list):
            print(f"  SKIP  {rel} (top-level JSON is not an array)")
            continue

        result = await session.execute(select(TaskPack).where(TaskPack.slug == meta["slug"]))
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = meta["name"]
            existing.description = meta["description"]
            existing.language = meta["language"]
            existing.task_count = len(tasks)
            existing.tasks_json = tasks
            print(f"  UPDATE  {meta['slug']} ({len(tasks)} tasks) <- {rel}")
        else:
            session.add(
                TaskPack(
                    slug=meta["slug"],
                    name=meta["name"],
                    description=meta["description"],
                    language=meta["language"],
                    task_count=len(tasks),
                    tasks_json=tasks,
                )
            )
            print(f"  INSERT  {meta['slug']} ({len(tasks)} tasks) <- {rel}")

    await session.commit()
    print("Done.")


async def main(dry_run: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        await seed(session, dry_run=dry_run)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed task packs from backend/tasks JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Discover and validate packs without committing DB changes")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
