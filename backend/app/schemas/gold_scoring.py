from pydantic import BaseModel, Field


class GoldScoreRequest(BaseModel):
    session_id: str


class TaskScore(BaseModel):
    task_id: str
    preference_correct: bool | None = None
    dimension_accuracy: dict[str, float] = Field(default_factory=dict)
    overall_score: float


class GoldScoreResponse(BaseModel):
    total_gold_tasks: int
    scored_tasks: int
    overall_accuracy: float
    task_scores: list[TaskScore]
