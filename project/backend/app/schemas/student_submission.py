"""学生端提交/订正/成长档案 Pydantic schema（Task 6）。

覆盖：
- 草稿保存与幂等提交请求。
- 教师退回/最终确认请求。
- 学生二次评价请求。
- 学生视角反馈、项目空间、成长档案响应。
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 草稿与提交 ──────────────────────────────────────────────

class DraftSaveRequest(BaseModel):
    """学生保存草稿（不创建版本，不触发状态机提交）。"""

    task_id: str = Field(..., description="任务 ID")
    content: Optional[str] = Field(None, description="作答内容")
    file_urls: list[str] = Field(default_factory=list, description="附件 URL 列表")


class IdempotentSubmitRequest(BaseModel):
    """幂等提交：同一 idempotency_key 重复提交不生成重复版本。"""

    task_id: str = Field(..., description="任务 ID")
    content: Optional[str] = Field(None, description="作答内容")
    file_urls: list[str] = Field(default_factory=list, description="附件 URL 列表")
    idempotency_key: str = Field(
        ..., max_length=64, description="客户端生成的幂等键（UUID）"
    )


class ResubmitRequest(BaseModel):
    """学生再提交（退回后再次提交）。"""

    content: Optional[str] = Field(None, description="作答内容")
    file_urls: list[str] = Field(default_factory=list, description="附件 URL 列表")
    idempotency_key: str = Field(
        ..., max_length=64, description="客户端生成的幂等键（UUID）"
    )


class ReassessRequest(BaseModel):
    """学生发起二次评价请求。"""

    reason: str = Field(..., min_length=1, max_length=1000, description="二次评价理由")


# ── 教师操作 ────────────────────────────────────────────────

class ReturnSubmissionRequest(BaseModel):
    """教师退回提交。"""

    teacher_comment: Optional[str] = Field(None, description="退回反馈（学生可见）")
    teacher_private_note: Optional[str] = Field(
        None, description="教师私有备注（学生不可见）"
    )


class FinalizeSubmissionRequest(BaseModel):
    """教师最终确认提交。"""

    teacher_comment: Optional[str] = Field(None, description="最终反馈（学生可见）")


# ── 响应 ────────────────────────────────────────────────────

class SubmissionRevisionResponse(BaseModel):
    """订正版本响应（学生视角隐藏 teacher_private_note）。"""

    id: str
    submission_id: Optional[str] = None
    attempt_number: int
    content: Optional[str] = None
    file_urls: Optional[list[Any]] = None
    idempotency_key: Optional[str] = None
    review_status: str
    teacher_comment: Optional[str] = None
    teacher_private_note: Optional[str] = None
    reassess_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class IdempotentSubmitResponse(BaseModel):
    """幂等提交响应：created=False 表示重复点击返回已有版本。"""

    submission_id: str
    revision_id: str
    attempt_number: int
    review_status: str
    created: bool = Field(..., description="是否为新建版本（False=重复点击）")


class StudentProjectViewResponse(BaseModel):
    """学生视角项目空间。"""

    project: dict[str, Any]
    problem: Optional[dict[str, Any]] = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    resources: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class StudentFeedbackResponse(BaseModel):
    """学生视角反馈视图。"""

    submission: dict[str, Any]
    revisions: list[dict[str, Any]] = Field(default_factory=list)
    evaluations: list[dict[str, Any]] = Field(default_factory=list)
    can_resubmit: bool = False
    can_request_reassess: bool = False


class GrowthPortfolioResponse(BaseModel):
    """成长档案。"""

    trajectories: list[dict[str, Any]] = Field(default_factory=list)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
