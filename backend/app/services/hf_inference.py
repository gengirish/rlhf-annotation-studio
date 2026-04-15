import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import Settings

MODEL_ID_RE = re.compile(r"^[\w\-.]+/[\w\-.]+(?:/[\w\-.]+)*(?::[\w\-]+)?$")

HUGGINGFACE_MODELS = [
    {"id": "Qwen/Qwen2.5-Coder-32B-Instruct", "name": "Qwen 2.5 Coder 32B", "tag": "code"},
    {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B", "tag": "general"},
    {"id": "meta-llama/Meta-Llama-3.1-8B-Instruct", "name": "Llama 3.1 8B", "tag": "general"},
    {
        "id": "mistralai/Mistral-Small-24B-Instruct-2501",
        "name": "Mistral Small 24B",
        "tag": "general",
    },
    {"id": "Qwen/Qwen2.5-7B-Instruct", "name": "Qwen 2.5 7B", "tag": "fast"},
]

NVIDIA_MODELS = [
    {
        "id": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "name": "Llama 3.3 Nemotron Super 49B",
        "tag": "reasoning",
    },
    {
        "id": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "name": "Llama 3.1 Nemotron Ultra 253B",
        "tag": "general",
    },
    {
        "id": "nvidia/llama-3.1-nemotron-nano-8b-v1",
        "name": "Llama 3.1 Nemotron Nano 8B",
        "tag": "fast",
    },
    {
        "id": "nvidia/nemotron-3-super-120b-a12b",
        "name": "Nemotron 3 Super 120B",
        "tag": "reasoning",
    },
    {
        "id": "meta/llama-3.3-70b-instruct",
        "name": "Llama 3.3 70B Instruct",
        "tag": "general",
    },
    {
        "id": "mistralai/mistral-small-24b-instruct-2501",
        "name": "Mistral Small 24B",
        "tag": "general",
    },
    {
        "id": "qwen/qwen2.5-coder-32b-instruct",
        "name": "Qwen 2.5 Coder 32B",
        "tag": "code",
    },
]

OPENROUTER_MODELS = [
    {
        "id": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "name": "Llama 3.3 Nemotron Super 49B v1.5",
        "tag": "reasoning",
    },
    {
        "id": "nvidia/llama-3.1-nemotron-70b-instruct",
        "name": "Llama 3.1 Nemotron 70B Instruct",
        "tag": "general",
    },
    {
        "id": "nvidia/nemotron-3-super-120b-a12b",
        "name": "Nemotron 3 Super 120B",
        "tag": "reasoning",
    },
    {
        "id": "nvidia/nemotron-nano-9b-v2",
        "name": "Nemotron Nano 9B v2",
        "tag": "fast",
    },
    {
        "id": "nvidia/nemotron-3-nano-30b-a3b",
        "name": "Nemotron 3 Nano 30B",
        "tag": "fast",
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct",
        "name": "Llama 3.3 70B Instruct",
        "tag": "general",
    },
    {
        "id": "qwen/qwen-2.5-coder-32b-instruct",
        "name": "Qwen 2.5 Coder 32B",
        "tag": "code",
    },
    {
        "id": "mistralai/mistral-small-24b-instruct-2501",
        "name": "Mistral Small 24B",
        "tag": "general",
    },
    {
        "id": "google/gemini-2.5-flash-preview",
        "name": "Gemini 2.5 Flash Preview",
        "tag": "fast",
    },
]

MODELS_BY_PROVIDER: dict[str, list[dict[str, str]]] = {
    "openrouter": OPENROUTER_MODELS,
    "huggingface": HUGGINGFACE_MODELS,
    "nvidia": NVIDIA_MODELS,
    "custom": [],
}

# Kept for backward compatibility with existing imports
AVAILABLE_MODELS = HUGGINGFACE_MODELS


def get_models_for_provider(provider: str) -> list[dict[str, str]]:
    return MODELS_BY_PROVIDER.get(provider, [])


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


def _build_headers(settings: Settings) -> dict[str, str]:
    token = settings.active_api_token
    if not token:
        provider = settings.inference_provider
        raise RuntimeError(f"API token is not configured for provider '{provider}'")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if settings.inference_provider == "openrouter":
        headers["HTTP-Referer"] = "https://rlhf-annotation-frontend.vercel.app"
        headers["X-Title"] = settings.openrouter_site_name
    return headers


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
    headers = _build_headers(settings)

    url = settings.active_base_url.rstrip("/") + "/chat/completions"
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
    headers = _build_headers(settings)

    url = settings.active_base_url.rstrip("/") + "/chat/completions"
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
