from pydantic import BaseModel


class AnnotationIssue(BaseModel):
    task_id: str
    field: str
    message: str
