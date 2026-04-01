import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import require_inference_caller
from app.config import Settings, get_settings
from app.schemas.inference import (
    InferenceCompleteRequest,
    InferenceCompleteResponse,
    InferenceSlotIn,
    InferenceSlotOut,
    InferenceStatusResponse,
)
from app.services.hf_inference import (
    get_models_for_provider,
    hf_chat_completion,
    hf_chat_completion_stream,
    validate_model_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["inference"])


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    seed: int | None = None


@router.get("/status", response_model=InferenceStatusResponse)
async def inference_status(settings: Settings = Depends(get_settings)) -> InferenceStatusResponse:
    token = settings.active_api_token
    configured = bool(token and token.strip())
    return InferenceStatusResponse(
        enabled=settings.inference_enabled,
        configured=configured,
        require_auth=settings.inference_require_auth,
        provider=settings.inference_provider,
    )


@router.get("/models")
async def list_models(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "provider": settings.inference_provider,
        "default": settings.active_default_model,
        "models": get_models_for_provider(settings.inference_provider),
    }


@router.post("/stream")
async def inference_stream(
    body: StreamRequest,
    settings: Settings = Depends(get_settings),
    _auth: None = Depends(require_inference_caller),
) -> StreamingResponse:
    if not settings.inference_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Inference is disabled")
    if not settings.active_api_token or not settings.active_api_token.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API token not configured for provider '{settings.inference_provider}'",
        )
    if len(body.prompt) > settings.inference_max_prompt_chars:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt exceeds max length ({settings.inference_max_prompt_chars} characters)",
        )

    model = (body.model or "").strip() or settings.active_default_model
    try:
        validate_model_id(model)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from None

    messages: list[dict[str, str]] = []
    if body.system:
        messages.append({"role": "system", "content": body.system})
    messages.append({"role": "user", "content": body.prompt})

    async def event_generator():
        try:
            async for token in hf_chat_completion_stream(
                settings,
                model=model,
                messages=messages,
                max_tokens=settings.inference_max_tokens,
                temperature=body.temperature,
                seed=body.seed,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.HTTPStatusError as e:
            err_msg = str(e)[:300]
            logger.warning("HF stream HTTP error: %s", err_msg)
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.warning("HF stream transport error: %s", e)
            err = "Request to inference provider failed or timed out"
            yield f"data: {json.dumps({'error': err})}\n\n"
        except Exception as e:
            logger.exception("HF stream unexpected error")
            yield f"data: {json.dumps({'error': str(e)[:300]})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _default_temperature(slot: InferenceSlotIn, idx: int) -> float:
    if slot.temperature is not None:
        return slot.temperature
    return 0.7 if idx == 0 else 0.75


async def _complete_one_slot(
    settings: Settings,
    prompt: str,
    system: str | None,
    slot: InferenceSlotIn,
    slot_index: int,
) -> InferenceSlotOut:
    label = slot.label or f"Response {slot_index + 1}"
    model = (slot.hf_model or "").strip() or settings.active_default_model
    try:
        validate_model_id(model)
    except ValueError as e:
        return InferenceSlotOut(label=label, model=model, error=str(e))

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    temp = _default_temperature(slot, slot_index)
    seed = slot.seed if slot.seed is not None else 1000 + slot_index

    try:
        text, used = await hf_chat_completion(
            settings,
            model=model,
            messages=messages,
            max_tokens=settings.inference_max_tokens,
            temperature=temp,
            seed=seed,
        )
    except httpx.HTTPStatusError as e:
        err_body = ""
        if e.response is not None:
            try:
                err_body = str(e.response.json())[:400]
            except Exception:
                err_body = (e.response.text or "")[:400]
        code = e.response.status_code if e.response else ""
        logger.warning("HF inference HTTP error: %s %s", code, err_body)
        return InferenceSlotOut(
            label=label,
            model=model,
            error=str(e)[:500] or "Inference provider error",
        )
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning("HF inference transport error: %s", e)
        return InferenceSlotOut(
            label=label,
            model=model,
            error="Request to inference provider failed or timed out",
        )
    except Exception as e:
        logger.exception("HF inference unexpected error")
        return InferenceSlotOut(label=label, model=model, error=str(e)[:500])

    return InferenceSlotOut(label=label, text=text or "", model=used or model, error=None)


@router.post("/complete", response_model=InferenceCompleteResponse)
async def inference_complete(
    body: InferenceCompleteRequest,
    settings: Settings = Depends(get_settings),
    _auth: None = Depends(require_inference_caller),
) -> InferenceCompleteResponse:
    if not settings.inference_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Inference is disabled")
    if not settings.active_api_token or not settings.active_api_token.strip():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"API token not configured for provider '{settings.inference_provider}'",
        )
    if len(body.prompt) > settings.inference_max_prompt_chars:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt exceeds max length ({settings.inference_max_prompt_chars} characters)",
        )

    tasks = [
        _complete_one_slot(settings, body.prompt, body.system, slot, i)
        for i, slot in enumerate(body.slots)
    ]
    results = await asyncio.gather(*tasks)
    return InferenceCompleteResponse(slots=list(results))
