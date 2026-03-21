from pydantic import BaseModel, Field


class InferenceSlotIn(BaseModel):
    label: str = ""
    hf_model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    seed: int | None = None


class InferenceCompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str | None = None
    slots: list[InferenceSlotIn] = Field(..., min_length=1, max_length=8)


class InferenceSlotOut(BaseModel):
    label: str
    text: str | None = None
    model: str | None = None
    error: str | None = None


class InferenceCompleteResponse(BaseModel):
    slots: list[InferenceSlotOut]


class InferenceStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    require_auth: bool
