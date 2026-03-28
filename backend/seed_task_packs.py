"""Seed task_packs table from JSON files in the repo tasks/ directory.

Usage (from backend/):
    python seed_task_packs.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.dirname(__file__))

from app.db import AsyncSessionLocal  # noqa: E402
from app.models.task_pack import TaskPack  # noqa: E402

_script_dir = Path(__file__).resolve().parent
TASKS_DIR = _script_dir / "tasks" if (_script_dir / "tasks").is_dir() else _script_dir.parent / "tasks"

PACK_META = [
    {
        "file": "debugging-exercises-python.json",
        "slug": "debugging-exercises-python",
        "name": "Python Debugging",
        "description": "9 debugging-focused comparison tasks covering mutable defaults, closures, generators, and scoping",
        "language": "python",
    },
    {
        "file": "debugging-exercises-java.json",
        "slug": "debugging-exercises-java",
        "name": "Java Debugging",
        "description": "9 Java debugging tasks with common pitfalls like == vs .equals(), ConcurrentModification, BigDecimal",
        "language": "java",
    },
    {
        "file": "debugging-exercises.json",
        "slug": "debugging-exercises",
        "name": "Debugging Exercises (Module 2)",
        "description": "Debugging comparison tasks from the AI Code Reviewer course Module 2 Session 3",
        "language": "java",
    },
    {
        "file": "code-review-comparisons.json",
        "slug": "code-review-comparisons",
        "name": "Code Review Comparisons",
        "description": "4 code review quality tasks — SQL injection, React optimization, API design, git commit messages",
        "language": "multi",
    },
    {
        "file": "safety-alignment.json",
        "slug": "safety-alignment",
        "name": "Safety and Alignment",
        "description": "3 safety-oriented evaluation tasks — medical safety, refusal quality, bias detection",
        "language": "general",
    },
    {
        "file": "hf-live-demo.json",
        "slug": "hf-live-demo",
        "name": "Hugging Face Live Demo",
        "description": "Live model comparison tasks using Hugging Face Inference API",
        "language": "python",
    },
    {
        "file": "m2-s05-javascript-debugging.json",
        "slug": "m2-s05-javascript-debugging",
        "name": "Session 05: JavaScript Debugging",
        "description": "9 JavaScript debugging tasks — type coercion, async/await, closures, this binding, truthy/falsy, Promise handling, strict equality",
        "language": "javascript",
    },
    {
        "file": "m2-s06-csharp-cpp-debugging.json",
        "slug": "m2-s06-csharp-cpp-debugging",
        "name": "Session 06: C# and C++ Debugging",
        "description": "3 debugging tasks — IDisposable resource leaks, async void, LINQ deferred execution, C++ memory leaks and RAII",
        "language": "csharp-cpp",
    },
    {
        "file": "m3-s07-cross-language-debugging.json",
        "slug": "m3-s07-cross-language-debugging",
        "name": "Session 07: Cross-Language Debugging",
        "description": "7 foundational debugging tasks — off-by-one, null reference, infinite loops, type mismatch, uninitialized variables, stack overflow, stack trace reading",
        "language": "multi",
    },
]


async def seed(session: AsyncSession) -> None:
    for meta in PACK_META:
        path = TASKS_DIR / meta["file"]
        if not path.exists():
            print(f"  SKIP  {meta['file']} (file not found at {path})")
            continue

        tasks = json.loads(path.read_text(encoding="utf-8"))

        result = await session.execute(select(TaskPack).where(TaskPack.slug == meta["slug"]))
        existing = result.scalar_one_or_none()

        if existing:
            existing.name = meta["name"]
            existing.description = meta["description"]
            existing.language = meta["language"]
            existing.task_count = len(tasks)
            existing.tasks_json = tasks
            print(f"  UPDATE  {meta['slug']} ({len(tasks)} tasks)")
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
            print(f"  INSERT  {meta['slug']} ({len(tasks)} tasks)")

    await session.commit()
    print("Done.")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
