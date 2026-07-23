from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PaperCreate(BaseModel):
    title: str
    class_ids: list[str] = []
    file_url: Optional[str] = None


class PaperUpdate(BaseModel):
    title: Optional[str] = None
    class_ids: Optional[list[str]] = None
    file_url: Optional[str] = None
    status: Optional[str] = None


class PaperResponse(BaseModel):
    id: str
    title: str
    teacher_id: str
    class_ids: list = []
    file_url: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AnswerKeyQuestion(BaseModel):
    index: int
    type: str = "essay"
    score: float = 10
    answer: str = ""
    rubric: str = ""


class AnswerKeyUpsert(BaseModel):
    questions: list[AnswerKeyQuestion] = []
    total_score: Optional[float] = None


class AnswerKeyResponse(BaseModel):
    id: str
    paper_id: str
    questions: list = []
    total_score: float
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaperSubmissionCreate(BaseModel):
    student_id: str
    file_url: Optional[str] = None
    content: Optional[str] = None


class PaperSubmissionResponse(BaseModel):
    id: str
    paper_id: str
    student_id: str
    file_url: Optional[str] = None
    content: Optional[str] = None
    ai_score: Optional[float] = None
    final_score: Optional[float] = None
    ai_comment: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PaperStatsResponse(BaseModel):
    total: int
    pending: int
    graded: int
    reviewed: int
    average_score: Optional[float] = None
