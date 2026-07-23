from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class LessonPlanCreate(BaseModel):
    title: str
    content: str
    subject: str
    grade: str
    topic: str
    duration: int = 45


class LessonPlanUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class LessonPlanResponse(BaseModel):
    id: str
    user_id: str
    title: str
    content: str
    subject: str
    grade: str
    topic: str
    duration: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
