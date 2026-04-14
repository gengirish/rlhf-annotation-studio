"""LLM-as-Judge reviewer for exam submissions.

Uses Google Gemini when GEMINI_API_KEY is configured, otherwise falls back
to the existing OpenAI-compatible inference provider.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.exam_rubric import (
    EXAM_REVIEW_RUBRIC_CRITERIA,
    VALID_RUBRIC_CRITERION_IDS,
    build_exam_judge_system_prompt,
    build_exam_judge_user_prompt,
)
from app.models.exam import Exam, ExamAttempt

log = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


async def _gemini_chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> tuple[str, str | None, int | None]:
    """Call the Gemini REST API with an OpenAI-style messages list."""
    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    system_parts: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = msg["role"]
        text = msg["content"]
        if role == "system":
            system_parts.append({"text": text})
        else:
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_parts:
        body["systemInstruction"] = {"parts": system_parts}

    url = _GEMINI_URL.format(model=model)
    timeout = httpx.Timeout(settings.inference_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=body, params={"key": api_key})

    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"Gemini API error ({resp.status_code}): {detail}")

    data = resp.json()
    candidates = data.get("candidates") or []
    text_out = ""
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text_out = "".join(p.get("text", "") for p in parts)

    usage = data.get("usageMetadata") or {}
    total_tokens = usage.get("totalTokenCount")
    tokens: int | None = int(total_tokens) if total_tokens is not None else None

    return text_out, model, tokens


def _isolate_json(text: str) -> str:
    text = text.strip()
    m = _JSON_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse_rubric_output(raw: str) -> dict[str, Any]:
    """Parse LLM output into rubric_scores, reasoning, confidence."""
    snippet = _isolate_json(raw)
    try:
        data = json.loads(snippet)
    except json.JSONDecodeError:
        return {
            "rubric_scores": {},
            "reasoning": f"Could not parse judge output. Raw: {raw[:500]}",
            "confidence": 0.0,
            "parse_error": True,
        }

    if not isinstance(data, dict):
        return {
            "rubric_scores": {},
            "reasoning": "Judge output was JSON but not an object.",
            "confidence": 0.0,
            "parse_error": True,
        }

    raw_scores = data.get("rubric_scores") or data.get("scores") or {}
    rubric_scores: dict[str, int] = {}
    if isinstance(raw_scores, dict):
        for k, v in raw_scores.items():
            if k in VALID_RUBRIC_CRITERION_IDS and isinstance(v, (int, float)):
                rubric_scores[k] = max(1, min(5, int(v)))

    reasoning = data.get("reasoning", "")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "No reasoning provided by the judge."

    conf = data.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(conf)))
    except (TypeError, ValueError):
        confidence = 0.0

    return {
        "rubric_scores": rubric_scores,
        "reasoning": reasoning.strip(),
        "confidence": confidence,
    }


def _response_texts_from_task(task: dict[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in task.get("responses") or []:
        if isinstance(r, dict):
            out.append((str(r.get("label", "")), str(r.get("text", ""))))
    return out


async def judge_exam_attempt(
    db: AsyncSession,
    attempt: ExamAttempt,
    settings: Settings | None = None,
    model: str | None = None,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Run LLM judge on every answered task in an exam attempt.

    Returns dict with:
        rubric_scores: aggregated {criterion_id: avg_score} (int 1-5)
        per_task: list of per-task results
        reasoning: combined reasoning text
        total_tokens: int
        total_latency_ms: int
        judge_model: str
    """
    settings = settings or get_settings()

    exam: Exam | None = attempt.exam
    if exam is None or exam.task_pack is None:
        from sqlalchemy import select

        from app.models.exam import Exam as ExamModel

        result = await db.execute(
            select(ExamModel)
            .options(selectinload(ExamModel.task_pack))
            .where(ExamModel.id == attempt.exam_id),
        )
        exam = result.scalar_one_or_none()
        if exam is None or exam.task_pack is None:
            raise ValueError("Exam or task pack not found")

    tasks_json = exam.task_pack.tasks_json if isinstance(exam.task_pack.tasks_json, list) else []
    answers = attempt.answers_json if isinstance(attempt.answers_json, dict) else {}

    use_gemini = bool(settings.gemini_api_key)
    if use_gemini:
        judge_model_id = (model or "").strip() or settings.gemini_model
        _chat_fn = _gemini_chat_completion
        log.info("Exam judge using Gemini model: %s", judge_model_id)
    else:
        from app.services.llm_judge_service import _judge_chat_completion

        judge_model_id = (model or "").strip() or settings.active_default_model
        _chat_fn = _judge_chat_completion
        log.info("Exam judge using inference provider: %s, model: %s", settings.inference_provider, judge_model_id)

    system_msg = build_exam_judge_system_prompt()

    per_task: list[dict[str, Any]] = []
    all_scores: dict[str, list[int]] = {c["id"]: [] for c in EXAM_REVIEW_RUBRIC_CRITERIA}
    total_tokens = 0
    total_latency = 0
    judge_model_used: str | None = None
    all_reasoning: list[str] = []

    for task in tasks_json:
        if not isinstance(task, dict):
            continue
        tid = str(task.get("id", "")).strip()
        if not tid or tid not in answers:
            continue

        candidate_answer = answers[tid]
        if not isinstance(candidate_answer, dict):
            continue

        response_texts = _response_texts_from_task(task)
        user_msg = build_exam_judge_user_prompt(
            task_prompt=str(task.get("prompt", "")),
            response_texts=response_texts,
            candidate_answer=candidate_answer,
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        t0 = time.perf_counter()
        raw_text, used_model, tokens = await _chat_fn(
            settings,
            model=judge_model_id,
            messages=messages,
            max_tokens=settings.inference_max_tokens,
            temperature=temperature,
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)

        if judge_model_used is None and used_model:
            judge_model_used = used_model
        if tokens:
            total_tokens += tokens
        total_latency += latency_ms

        parsed = _parse_rubric_output(raw_text)
        task_title = str(task.get("title", tid))

        task_result: dict[str, Any] = {
            "task_id": tid,
            "task_title": task_title,
            "rubric_scores": parsed["rubric_scores"],
            "reasoning": parsed["reasoning"],
            "confidence": parsed["confidence"],
            "tokens": tokens,
            "latency_ms": latency_ms,
        }
        per_task.append(task_result)

        task_scores = parsed["rubric_scores"]
        for cid in all_scores:
            if cid in task_scores:
                all_scores[cid].append(task_scores[cid])

        if parsed.get("reasoning"):
            all_reasoning.append(f"**{task_title}**: {parsed['reasoning']}")

    aggregated: dict[str, int] = {}
    for cid, scores in all_scores.items():
        if scores:
            aggregated[cid] = max(1, min(5, round(sum(scores) / len(scores))))

    combined_reasoning = "\n\n".join(all_reasoning) if all_reasoning else "No tasks were evaluated."

    return {
        "rubric_scores": aggregated,
        "per_task": per_task,
        "reasoning": combined_reasoning,
        "total_tokens": total_tokens,
        "total_latency_ms": total_latency,
        "judge_model": judge_model_used or judge_model_id,
    }
