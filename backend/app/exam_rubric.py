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


def build_rubric_criteria_description() -> str:
    """Format rubric criteria for inclusion in an LLM judge prompt."""
    lines: list[str] = []
    for c in EXAM_REVIEW_RUBRIC_CRITERIA:
        lines.append(f"- **{c['title']}** (id: `{c['id']}`, integer 1–5): {c['description']}")
    return "\n".join(lines)


def build_exam_judge_system_prompt() -> str:
    return (
        "You are an expert exam reviewer for an RLHF Annotation Studio. "
        "You evaluate candidate answers to coding/debugging tasks against a structured rubric. "
        "Respond with a single JSON object only — no markdown code fences, no text before or after."
    )


def build_exam_judge_user_prompt(
    task_prompt: str,
    response_texts: list[tuple[str, str]],
    candidate_answer: dict[str, Any],
) -> str:
    """Build the user message for the LLM judge.

    Args:
        task_prompt: The original task prompt shown to the candidate.
        response_texts: List of (label, text) for each response option.
        candidate_answer: The candidate's annotation_json (preference, dimensions, justification).
    """
    rubric_desc = build_rubric_criteria_description()

    sections = [f"## Task Prompt\n{task_prompt}\n"]

    if response_texts:
        for label, text in response_texts:
            sections.append(f"## {label}\n{text}\n")

    sections.append("## Candidate's Answer")
    pref = candidate_answer.get("preference")
    if pref is not None:
        sections.append(f"Preference: {pref}")
    dims = candidate_answer.get("dimensions")
    if isinstance(dims, dict) and dims:
        dims_str = ", ".join(f"{k}: {v}" for k, v in dims.items())
        sections.append(f"Dimension ratings: {dims_str}")
    justification = candidate_answer.get("justification", "")
    if justification:
        sections.append(f"Justification: {justification}")
    sections.append("")

    rubric_ids = ", ".join(f'"{c["id"]}"' for c in EXAM_REVIEW_RUBRIC_CRITERIA)

    sections.append(f"## Evaluation Rubric\n{rubric_desc}\n")
    sections.append(
        "Evaluate the candidate's answer against the rubric above. "
        "Provide your assessment as a JSON object:\n"
        f'{{"rubric_scores": {{{rubric_ids}: <integer 1-5 each>}}, '
        '"reasoning": "concise overall assessment of the answer quality", '
        '"confidence": <float 0.0 to 1.0>}\n\n'
        "Use the exact rubric criterion IDs as keys. "
        "Each score must be an integer from 1 (poor) to 5 (excellent)."
    )

    return "\n".join(sections)


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
