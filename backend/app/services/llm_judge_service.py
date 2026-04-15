from __future__ import annotations

import json
import re
import time
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.annotator import Annotator
from app.models.llm_evaluation import LLMEvaluation
from app.models.task_pack import TaskPack
from app.schemas.llm_judge import (
    HumanOverrideRequest,
    JudgeBatchResponse,
    JudgeConfig,
    JudgeResult,
    JudgeTaskRequest,
)

DEFAULT_SYSTEM = (
    "You are an expert AI response evaluator. Follow the evaluation instructions exactly. "
    "Respond with a single JSON object only — no markdown code fences, no text before or after."
)

DEFAULT_COMPARISON_USER = (
    "You are an expert AI response evaluator. "
    "Evaluate the following responses to the user's prompt.\n\n"
    "## User Prompt\n{prompt}\n\n"
    "## Response A\n{response_a}\n\n"
    "## Response B\n{response_b}\n\n"
    "## Evaluation Criteria\n{dimensions_description}\n\n"
    "Evaluate both responses and provide your assessment as JSON:\n"
    '{{"preference": 0 or 1 (0 if A is better, 1 if B is better), '
    '"dimensions": {{"dimension_name": integer rating}}, '
    '"reasoning": "concise explanation", '
    '"confidence": a number from 0.0 to 1.0}}\n\n'
    "Use the exact dimension names from the criteria. "
    "Integer ratings must fall within each dimension's scale."
)

DEFAULT_RATING_USER = (
    "You are an expert AI response evaluator. "
    "Evaluate the following model response to the user's prompt.\n\n"
    "## User Prompt\n{prompt}\n\n"
    "## Model Response\n{response}\n\n"
    "## Evaluation Criteria\n{dimensions_description}\n\n"
    "Provide your assessment as JSON:\n"
    '{{"preference": null, '
    '"dimensions": {{"dimension_name": integer rating}}, '
    '"reasoning": "concise explanation", '
    '"confidence": a number from 0.0 to 1.0}}\n\n'
    "Use the exact dimension names from the criteria. "
    "Integer ratings must fall within each dimension's scale."
)

DEFAULT_RANKING_USER = (
    "You are an expert AI response evaluator. "
    "The user prompt is followed by several candidate responses. "
    "Rank them from best to worst.\n\n"
    "## User Prompt\n{prompt}\n\n"
    "## Candidate responses\n{responses_block}\n\n"
    "## Evaluation Criteria\n{dimensions_description}\n\n"
    "Provide your assessment as JSON:\n"
    '{{"preference": null, '
    '"ranking": [0, 1, 2, ...] (0-based best-to-worst), '
    '"dimensions": {{"dimension_name": integer rating}} '
    "(rate the best response), "
    '"reasoning": "concise explanation", '
    '"confidence": a number from 0.0 to 1.0}}\n\n'
    "Use the exact dimension names from the criteria."
)


def _extract_message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _filter_dimensions(task: dict[str, Any], config: JudgeConfig) -> list[dict[str, Any]]:
    dims = list(task.get("dimensions") or [])
    if config.dimensions:
        allowed = set(config.dimensions)
        dims = [d for d in dims if isinstance(d, dict) and d.get("name") in allowed]
    return dims


def build_dimensions_description(task: dict[str, Any], config: JudgeConfig) -> str:
    dims = _filter_dimensions(task, config)
    if not dims:
        return "No specific rubric dimensions were provided; give a holistic quality assessment."
    lines: list[str] = []
    for d in dims:
        name = str(d.get("name", "unknown"))
        desc = str(d.get("description", "")).strip()
        try:
            scale = int(d.get("scale", 5))
        except (TypeError, ValueError):
            scale = 5
        lines.append(f"- **{name}** (integer 1–{scale}): {desc}")
    return "\n".join(lines)


def _safe_format(template: str, mapping: dict[str, str]) -> str:
    class _M(dict):
        def __missing__(self, key: str) -> str:
            return ""

    return template.format_map(_M(mapping))


def _response_texts(task: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for r in task.get("responses") or []:
        if isinstance(r, dict):
            out.append(str(r.get("text", "")))
        else:
            out.append(str(r))
    return out


def build_judge_prompt(task: dict[str, Any], config: JudgeConfig) -> tuple[str, str]:
    """Return (system_message, user_message) for the judge call."""
    system = DEFAULT_SYSTEM
    prompt = str(task.get("prompt", "")).strip()
    dims_desc = build_dimensions_description(task, config)
    task_type = str(task.get("type", "comparison")).lower()

    if config.prompt_template:
        texts = _response_texts(task)
        mapping: dict[str, str] = {
            "prompt": prompt,
            "dimensions_description": dims_desc,
            "response_a": texts[0] if len(texts) > 0 else "",
            "response_b": texts[1] if len(texts) > 1 else "",
            "response": texts[0] if len(texts) > 0 else "",
        }
        for i, t in enumerate(texts):
            mapping[f"response_{i}"] = t
        user = _safe_format(config.prompt_template, mapping)
        return system, user

    if task_type == "rating":
        texts = _response_texts(task)
        response = texts[0] if texts else ""
        user = _safe_format(
            DEFAULT_RATING_USER,
            {"prompt": prompt, "response": response, "dimensions_description": dims_desc},
        )
        return system, user

    if task_type == "ranking":
        texts = _response_texts(task)
        blocks: list[str] = []
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i, txt in enumerate(texts):
            label = labels[i] if i < len(labels) else str(i)
            blocks.append(f"### Response {label} (index {i})\n{txt}")
        responses_block = "\n\n".join(blocks) if blocks else "(no responses)"
        user = _safe_format(
            DEFAULT_RANKING_USER,
            {
                "prompt": prompt,
                "responses_block": responses_block,
                "dimensions_description": dims_desc,
            },
        )
        return system, user

    # comparison (default)
    texts = _response_texts(task)
    response_a = texts[0] if len(texts) > 0 else ""
    response_b = texts[1] if len(texts) > 1 else ""
    user = _safe_format(
        DEFAULT_COMPARISON_USER,
        {
            "prompt": prompt,
            "response_a": response_a,
            "response_b": response_b,
            "dimensions_description": dims_desc,
        },
    )
    return system, user


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _isolate_json_object(text: str) -> str:
    text = text.strip()
    m = _JSON_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_judge_llm_output(raw: str, task_id: str) -> tuple[JudgeResult, dict[str, Any]]:
    """Parse model output into JudgeResult and a dict suitable for `evaluation_json`."""
    snippet = _isolate_json_object(raw)
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError as exc:
        preview = raw.strip()[:400]
        reasoning = f"Could not parse judge output as JSON ({exc!s}). Raw preview: {preview!r}"
        payload = {
            "preference": None,
            "dimensions": None,
            "reasoning": reasoning,
            "parse_error": True,
        }
        return (
            JudgeResult(
                task_id=task_id,
                preference=None,
                dimensions=None,
                reasoning=reasoning,
                confidence=0.0,
            ),
            payload,
        )

    if not isinstance(data, dict):
        reasoning = "Judge output was JSON but not an object."
        payload = {
            "preference": None,
            "dimensions": None,
            "reasoning": reasoning,
            "parse_error": True,
        }
        return (
            JudgeResult(
                task_id=task_id,
                preference=None,
                dimensions=None,
                reasoning=reasoning,
                confidence=0.0,
            ),
            payload,
        )

    pref = data.get("preference")
    preference: int | None
    if pref is None:
        preference = None
    elif isinstance(pref, bool):
        preference = int(pref)
    elif isinstance(pref, int):
        preference = pref
    else:
        preference = None

    dims_raw = data.get("dimensions")
    dimensions: dict[str, int] | None = None
    if isinstance(dims_raw, dict):
        dimensions = {}
        for k, v in dims_raw.items():
            if isinstance(k, str) and isinstance(v, (int, float)):
                dimensions[k] = int(v)

    reasoning = data.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "No reasoning provided by the judge."
    else:
        reasoning = reasoning.strip()

    conf_raw = data.get("confidence", 0.0)
    try:
        confidence = float(conf_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    eval_json: dict[str, Any] = {
        "preference": preference,
        "dimensions": dimensions,
        "reasoning": reasoning,
        "confidence": confidence,
    }
    if "ranking" in data:
        eval_json["ranking"] = data["ranking"]

    return (
        JudgeResult(
            task_id=task_id,
            preference=preference,
            dimensions=dimensions,
            reasoning=reasoning,
            confidence=confidence,
        ),
        eval_json,
    )


def extract_confidence_from_output(raw: str) -> float:
    """Best-effort confidence extraction for tests and partial outputs."""
    _, ev = parse_judge_llm_output(raw, task_id="")
    c = ev.get("confidence")
    if isinstance(c, (int, float)):
        return max(0.0, min(1.0, float(c)))
    return 0.0


async def _judge_chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> tuple[str, str | None, int | None]:
    """OpenAI-compatible chat call; no strict model-id validation."""
    from app.services.hf_inference import _build_headers

    headers = _build_headers(settings)
    url = settings.active_base_url.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    timeout = httpx.Timeout(settings.inference_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=body, headers=headers)

    if response.status_code >= 400:
        try:
            err = response.json()
            detail = err.get("error") or err.get("message") or response.text
            if isinstance(detail, dict):
                detail = detail.get("message", str(detail))
        except Exception:
            detail = response.text[:500] or response.reason_phrase
        raise httpx.HTTPStatusError(
            f"Inference error: {detail}",
            request=response.request,
            response=response,
        ) from None

    data = response.json()
    text = _extract_message_text(data)
    used_model = data.get("model")
    used_str = used_model if isinstance(used_model, str) else None
    usage = data.get("usage") or {}
    total = usage.get("total_tokens")
    tokens: int | None = int(total) if isinstance(total, (int, float)) else None
    return text, used_str, tokens


async def evaluate_task(
    task: dict[str, Any],
    config: JudgeConfig,
    settings: Settings,
) -> tuple[JudgeResult, dict[str, Any], str, str, int | None, int]:
    """
    Call the judge model and parse output.

    Returns:
        judge_result, evaluation_json, judge_model_id, prompt_record, tokens_used, latency_ms
    """
    tid = str(task.get("id", "")).strip() or "unknown-task"
    system_msg, user_msg = build_judge_prompt(task, config)
    prompt_record = f"{system_msg}\n\n---\n\n{user_msg}"

    model = (config.model or "").strip() or settings.active_default_model
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    t0 = time.perf_counter()
    raw, used_model, tokens = await _judge_chat_completion(
        settings,
        model=model,
        messages=messages,
        max_tokens=settings.inference_max_tokens,
        temperature=config.temperature,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    judge_model = (used_model or model).strip()

    result, eval_json = parse_judge_llm_output(raw, task_id=tid)
    return result, eval_json, judge_model, prompt_record, tokens, latency_ms


async def evaluate_batch(
    db: AsyncSession,
    body: JudgeTaskRequest,
    settings: Settings | None = None,
) -> JudgeBatchResponse:
    settings = settings or get_settings()
    pack = await db.get(TaskPack, body.task_pack_id)
    if pack is None:
        raise ValueError("Task pack not found")

    tasks_raw = list(pack.tasks_json or [])
    wanted: set[str] | None = None
    if body.task_ids is not None:
        wanted = {str(x) for x in body.task_ids}

    results: list[JudgeResult] = []
    total_tokens = 0
    total_latency = 0
    judge_model_used: str | None = None

    for task in tasks_raw:
        if not isinstance(task, dict):
            continue
        tid = str(task.get("id", "")).strip()
        if not tid:
            continue
        if wanted is not None and tid not in wanted:
            continue

        jr, eval_json, jm, prompt_record, tokens, lat = await evaluate_task(
            task, body.config, settings
        )
        if judge_model_used is None:
            judge_model_used = jm
        if tokens is not None:
            total_tokens += tokens
        total_latency += lat

        existing = await db.execute(
            select(LLMEvaluation)
            .where(LLMEvaluation.task_pack_id == body.task_pack_id)
            .where(LLMEvaluation.task_id == tid)
            .order_by(LLMEvaluation.updated_at.desc())
            .limit(1),
        )
        row = existing.scalars().first()
        if row is None:
            row = LLMEvaluation(
                task_pack_id=body.task_pack_id,
                task_id=tid,
                judge_model=jm,
                judge_prompt_template=prompt_record,
                evaluation_json=eval_json,
                confidence=jr.confidence,
                status="pending",
                tokens_used=tokens,
                latency_ms=lat,
            )
            db.add(row)
        else:
            row.judge_model = jm
            row.judge_prompt_template = prompt_record
            row.evaluation_json = eval_json
            row.confidence = jr.confidence
            row.tokens_used = tokens
            row.latency_ms = lat
            row.status = "pending"
            row.human_override = None
            row.human_override_by = None

        results.append(jr)

    await db.commit()

    return JudgeBatchResponse(
        task_pack_id=body.task_pack_id,
        results=results,
        judge_model=judge_model_used or (body.config.model or settings.active_default_model),
        total_tokens=total_tokens,
        total_latency_ms=total_latency,
    )


async def apply_human_override(
    db: AsyncSession,
    evaluation_id: UUID,
    user: Annotator,
    override: HumanOverrideRequest,
) -> LLMEvaluation | None:
    row = await db.get(LLMEvaluation, evaluation_id)
    if row is None:
        return None

    merged: dict[str, Any] = dict(row.human_override) if row.human_override else {}
    if override.preference is not None:
        merged["preference"] = override.preference
    if override.dimensions is not None:
        merged["dimensions"] = dict(override.dimensions)
    if override.reasoning is not None:
        merged["reasoning"] = override.reasoning

    row.human_override = merged
    row.human_override_by = user.id
    row.status = "overridden"
    await db.commit()
    await db.refresh(row)
    return row
