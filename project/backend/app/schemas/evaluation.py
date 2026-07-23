from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class EvaluationCreate(BaseModel):
    task_id: str
    student_id: str
    score: int
    comment: Optional[str] = None
    eval_type: str = "teacher"


class EvaluationUpdate(BaseModel):
    score: Optional[int] = None
    comment: Optional[str] = None


class EvaluationResponse(BaseModel):
    id: str
    task_id: str
    student_id: str
    evaluator_id: str
    score: int
    comment: Optional[str] = None
    eval_type: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
