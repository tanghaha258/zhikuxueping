from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LessonPlanRequest(BaseModel):
    subject: str
    grade: str
    topic: str
    duration: int = 45
    objectives: Optional[str] = None
    additional: Optional[str] = None


class LessonPlanFromProjectRequest(BaseModel):
    """基于项目结构化上下文的 AI 备课（计划 Task 5 验收标准 4）。"""

    project_id: str


class LessonPlanResponse(BaseModel):
    content: str
    title: str


class AiProviderCreate(BaseModel):
    name: str
    api_url: str
    model: str
    api_key: str


class AiProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    status: Optional[str] = None


class AiProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    api_url: str
    model: str
    api_key: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @staticmethod
    def mask_key(key: str) -> str:
        if not key:
            return ""
        if len(key) > 8:
            return key[:4] + "****" + key[-4:]
        return key[:4] + "****"
