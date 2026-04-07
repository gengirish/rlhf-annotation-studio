from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.llm_judge import HumanOverrideRequest, JudgeConfig
from app.services.llm_judge_service import (
    apply_human_override,
    build_judge_prompt,
    extract_confidence_from_output,
    parse_judge_llm_output,
)


def _comparison_task() -> dict:
    return {
        "id": "cr-1",
        "type": "comparison",
        "prompt": "Fix this code.",
        "responses": [
            {"label": "Response A", "text": "Use parameterized queries."},
            {"label": "Response B", "text": "Add try/except."},
        ],
        "dimensions": [
            {"name": "Security", "description": "Security awareness", "scale": 5},
            {"name": "Clarity", "description": "Clear explanation", "scale": 5},
        ],
    }


def _rating_task() -> dict:
    return {
        "id": "rate-1",
        "type": "rating",
        "prompt": "Rate this API design.",
        "responses": [{"label": "R1", "text": "Use REST with HATEOAS."}],
        "dimensions": [{"name": "Design", "description": "REST quality", "scale": 4}],
    }


def test_build_judge_prompt_comparison_includes_responses_and_dimensions() -> None:
    cfg = JudgeConfig()
    system, user = build_judge_prompt(_comparison_task(), cfg)
    assert "JSON object" in system or "JSON" in system
    assert "Fix this code." in user
    assert "Response A" in user or "parameterized" in user
    assert "Security" in user and "Clarity" in user


def test_build_judge_prompt_rating_single_response_template() -> None:
    cfg = JudgeConfig()
    system, user = build_judge_prompt(_rating_task(), cfg)
    assert "Model Response" in user
    assert "HATEOAS" in user
    assert '"preference": null' in user or "preference" in user


def test_build_judge_prompt_filters_dimensions_when_configured() -> None:
    cfg = JudgeConfig(dimensions=["Security"])
    _system, user = build_judge_prompt(_comparison_task(), cfg)
    assert "Security" in user
    assert "Clarity" not in user


def test_parse_judge_llm_output_valid_json() -> None:
    raw = '{"preference": 0, "dimensions": {"Security": 5}, "reasoning": "A is safer.", "confidence": 0.9}'
    result, ev = parse_judge_llm_output(raw, "t1")
    assert result.task_id == "t1"
    assert result.preference == 0
    assert result.dimensions == {"Security": 5}
    assert result.reasoning == "A is safer."
    assert result.confidence == pytest.approx(0.9)
    assert ev["confidence"] == pytest.approx(0.9)


def test_parse_judge_llm_output_markdown_fenced() -> None:
    raw = """Here is the result:
```json
{"preference": 1, "dimensions": {}, "reasoning": "ok", "confidence": 0.5}
```
"""
    result, _ev = parse_judge_llm_output(raw, "x")
    assert result.preference == 1
    assert result.confidence == pytest.approx(0.5)


def test_parse_judge_malformed_json_graceful() -> None:
    raw = "not json at all {{{"
    result, ev = parse_judge_llm_output(raw, "bad")
    assert result.confidence == 0.0
    assert result.preference is None
    assert "parse" in result.reasoning.lower() or "json" in result.reasoning.lower()
    assert ev.get("parse_error") is True


def test_extract_confidence_from_output() -> None:
    assert extract_confidence_from_output('{"confidence": 0.37, "reasoning": "x"}') == pytest.approx(0.37)
    assert extract_confidence_from_output("garbage") == 0.0


@pytest.mark.asyncio
async def test_apply_human_override_merges_fields() -> None:
    eid = uuid4()
    uid = uuid4()
    row = SimpleNamespace(
        id=eid,
        human_override=None,
        human_override_by=None,
        status="pending",
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=row)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    user = SimpleNamespace(id=uid)
    req = HumanOverrideRequest(preference=1, reasoning="Human correction")
    out = await apply_human_override(db, eid, user, req)

    assert out is row
    assert row.status == "overridden"
    assert row.human_override_by == uid
    assert row.human_override == {"preference": 1, "reasoning": "Human correction"}
    db.commit.assert_awaited_once()
