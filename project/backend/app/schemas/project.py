from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    grade: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    subject_ids: list[str] = []
    class_ids: list[str] = []


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    grade: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    status: str
    creator_id: str
    school_id: Optional[str] = None
    grade: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_template: bool
    class_ids: list[str] = []
    # 核心闭环扩展字段（增量暴露，历史项目为 None，向后兼容）
    project_type: Optional[str] = None
    core_subject_id: Optional[str] = None
    review_status: Optional[str] = None
    data_origin: Optional[str] = None
    created_at: Optional[datetime] = None
    # 结项/归档扩展字段（Task 9）
    teacher_reflection: Optional[str] = None
    reopen_reason: Optional[str] = None
    reopened_at: Optional[datetime] = None
    reopened_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectReopenRequest(BaseModel):
    """重新开放归档项目请求（school_admin 专用）。

    reason 必填且留痕，便于审计追溯（计划 Task 9 验收）。
    """
    reason: str


class ProjectReflectionRequest(BaseModel):
    """教师结项反思请求。"""
    reflection_text: str


class ProjectListResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    grade: Optional[str] = None
    creator_id: str
    # 列表页需展示核心学科与审核状态（计划 3.3）
    core_subject_id: Optional[str] = None
    review_status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
