import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings

MODEL_ID_RE = re.compile(r"^[\w\-.]+/[\w\-.]+(?::[\w\-]+)?$")

AVAILABLE_MODELS = [
    {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Qwen 2.5 Coder 32B", "tag": "code"},
    {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen 2.5 7B", "tag": "general"},
    {"id": "mistralai/Mistral-7B-Instruct-v0.3", "name": "Mistral 7B v0.3", "tag": "general"},
    {"id": "meta-llama/Llama-3.1-8B-Instruct", "name": "Llama 3.1 8B", "tag": "general"},
    {"id": "microsoft/Phi-3-mini-4k-instruct", "name": "Phi-3 Mini", "tag": "fast"},
]


def validate_model_id(model: str) -> None:
    if not MODEL_ID_RE.match(model):
        msg = "Invalid model id (expected 'org/model' or 'org/model:suffix')"
        raise ValueError(msg)


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


async def hf_chat_completion(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    seed: int | None,
) -> tuple[str, str | None]:
    validate_model_id(model)
    token = settings.hf_api_token
    if not token:
        raise RuntimeError("HF API token is not configured")

    url = settings.hf_router_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if seed is not None:
        body["seed"] = seed

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
            f"HF inference error: {detail}",
            request=response.request,
            response=response,
        ) from None

    data = response.json()
    text = _extract_message_text(data)
    used_model = data.get("model")
    return text, used_model if isinstance(used_model, str) else None


async def hf_chat_completion_stream(
    settings: Settings,
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    seed: int | None,
) -> AsyncIterator[str]:
    validate_model_id(model)
    token = settings.hf_api_token
    if not token:
        raise RuntimeError("HF API token is not configured")

    url = settings.hf_router_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if seed is not None:
        body["seed"] = seed

    timeout = httpx.Timeout(settings.inference_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                try:
                    err = json.loads(error_body)
                    detail = err.get("error") or err.get("message") or error_body.decode()[:500]
                    if isinstance(detail, dict):
                        detail = detail.get("message", str(detail))
                except Exception:
                    detail = error_body.decode()[:500]
                raise httpx.HTTPStatusError(
                    f"HF inference error: {detail}",
                    request=response.request,
                    response=response,
                ) from None

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
