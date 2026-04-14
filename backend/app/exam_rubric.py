"""Shared definition for structured exam review rubric (1–5 per criterion)."""

from __future__ import annotations

from typing import Any, TypedDict


class RubricCriterion(TypedDict):
    id: str
    title: str
    description: str


# Default rubric for technical / debugging-style exam answers (matches product UI).
EXAM_REVIEW_RUBRIC_CRITERIA: list[RubricCriterion] = [
    {
        "id": "root_cause_identification",
        "title": "Root Cause Identification",
        "description": (
            "Does it correctly identify reference vs value comparison as the root cause?"
        ),
    },
    {
        "id": "explanation_depth",
        "title": "Explanation Depth",
        "description": (
            "Does it explain String interning, heap allocation, and why == works with literals?"
        ),
    },
    {
        "id": "fix_correctness",
        "title": "Fix Correctness",
        "description": (
            "Is the fix correct, robust, and does it solve the general problem "
            "(not just this test case)?"
        ),
    },
    {
        "id": "null_safety",
        "title": "Null Safety",
        "description": (
            "Does it address potential NullPointerException when calling .equals() "
            "on a possibly null reference?"
        ),
    },
    {
        "id": "educational_value",
        "title": "Educational Value",
        "description": "Would this help a developer avoid == for objects in all future code?",
    },
]

VALID_RUBRIC_CRITERION_IDS = frozenset(c["id"] for c in EXAM_REVIEW_RUBRIC_CRITERIA)


def normalize_rubric_scores(raw: dict[str, Any] | None) -> dict[str, int]:
    """Validate and return only known keys with integer scores in 1..5."""
    if not raw:
        return {}
    out: dict[str, int] = {}
    for key, val in raw.items():
        if key not in VALID_RUBRIC_CRITERION_IDS:
            raise ValueError(f"Unknown rubric criterion: {key!r}")
        if not isinstance(val, int) or isinstance(val, bool):
            raise ValueError(f"Score for {key!r} must be an integer from 1 to 5")
        if val < 1 or val > 5:
            raise ValueError(f"Score for {key!r} must be from 1 to 5")
        out[key] = val
    return out


def rubric_rows_from_stored(stored: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build display rows: every criterion with score from JSON or None."""
    s = stored or {}
    rows: list[dict[str, Any]] = []
    for c in EXAM_REVIEW_RUBRIC_CRITERIA:
        raw = s.get(c["id"])
        score = raw if isinstance(raw, int) and not isinstance(raw, bool) and 1 <= raw <= 5 else None
        rows.append(
            {
                "id": c["id"],
                "title": c["title"],
                "description": c["description"],
                "score": score,
            },
        )
    return rows
