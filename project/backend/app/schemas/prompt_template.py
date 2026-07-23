from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PromptTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    subject: str = Field(..., min_length=1, max_length=50, description="适用学科")
    exam_type: str = Field("quiz", description="考试类型: quiz/midterm/final")
    template: str = Field(..., min_length=1, description="提示词模板内容")
    description: Optional[str] = Field(None, description="模板说明")
    is_active: bool = Field(True, description="是否启用")


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    subject: Optional[str] = Field(None, min_length=1, max_length=50)
    exam_type: Optional[str] = None
    template: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    subject: str
    exam_type: str
    template: str
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
