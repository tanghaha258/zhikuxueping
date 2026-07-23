from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


EXAM_TYPES = ["quiz", "midterm", "final", "general"]
EXAM_TYPE_LABELS = {"quiz": "周测", "midterm": "期中考试", "final": "期末考试", "general": "通用"}


class SectionItem(BaseModel):
    """单个题型配置"""
    id: str = ""
    label: str = ""
    type: str = "choice"
    instruction: str = ""
    sub_type: Optional[str] = None
    count: int = 1
    score_per: float = 1.0
    total: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class PaperTemplateCreate(BaseModel):
    name: str
    exam_type: str = "general"
    subject: str
    grade: str
    total_score: float = 100.0
    config: Optional[str] = None
    sections: Optional[str] = None


class PaperTemplateUpdate(BaseModel):
    name: Optional[str] = None
    exam_type: Optional[str] = None
    subject: Optional[str] = None
    grade: Optional[str] = None
    total_score: Optional[float] = None
    config: Optional[str] = None
    sections: Optional[str] = None


class PaperTemplateResponse(BaseModel):
    id: str
    name: str
    exam_type: str
    subject: str
    grade: str
    total_score: float = 100.0
    config: Optional[str] = None
    sections: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GeneratePaperRequest(BaseModel):
    subject: str
    grade: str
    template_id: Optional[str] = None
    title: Optional[str] = None
    difficulty: str = "medium"
    knowledge_points: Optional[list[str]] = None
    sections: Optional[str] = None
    exam_type: Optional[str] = "quiz"


class GeneratePaperGovernedRequest(BaseModel):
    """基于项目结构化上下文的治理层出卷（计划 Task 5）。"""

    project_id: str
    output_type: str = "试卷"


class AiGeneratedPaperUpdate(BaseModel):
    title: Optional[str] = None
    questions: Optional[str] = None
    total_score: Optional[float] = None
    duration: Optional[int] = None


class AiGeneratedPaperResponse(BaseModel):
    id: str
    teacher_id: str
    template_id: Optional[str] = None
    subject: str
    grade: str
    title: str
    difficulty: str
    knowledge_points: Optional[str] = None
    questions: Optional[str] = None
    total_score: float
    duration: int
    status: str
    formatted_html: Optional[str] = None
    template_type: Optional[str] = None
    template_config: Optional[str] = None
    exported_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FormatRequest(BaseModel):
    template_type: str = "midterm"
    subject: str = ""


class FormatResponse(BaseModel):
    id: str
    formatted_html: str
    template_type: str


class GeneratePaperResponse(BaseModel):
    id: str
    title: str
    questions: str
    total_score: float
    duration: int
    difficulty: str
    template_id: Optional[str] = None
    status: str
    formatted_html: Optional[str] = None
    template_type: Optional[str] = None
    template_config: Optional[str] = None
    warning: Optional[str] = None


class KnowledgePointCreate(BaseModel):
    subject: str
    grade: str
    name: str
    description: Optional[str] = None
    sort_order: int = 0


class KnowledgePointResponse(BaseModel):
    id: str
    subject: str
    grade: str
    name: str
    description: Optional[str] = None
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
