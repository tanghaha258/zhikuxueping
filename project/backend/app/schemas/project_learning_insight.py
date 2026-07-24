"""项目学情诊断 Pydantic 模型（Task 6）。

字段命名与后端 snake_case 一致；HTTP 响应经前端拦截器转为 camelCase。
诊断只能由真实数据计算：无证据时返回 ``insufficient_evidence`` 与空 segments，
绝不为随机画像或伪成功。``source_counts`` 记录四类数据来源（前测/提交/已发布评价/
题目作答）数量，用于校验诊断是否基于真实证据。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InsightSourceCounts(BaseModel):
    """四类数据来源计数，不伪造。"""

    pre_test: int = 0
    submissions: int = 0
    evaluations: int = 0
    question_answers: int = 0


class InsightSegment(BaseModel):
    """学生分层建议：基于真实评价分数分组，非随机生成。"""

    name: str
    student_count: int
    mastery_range: Optional[list[float]] = None  # [下限, 上限]


class InsightWeakPoint(BaseModel):
    """薄弱点：来自真实低分组学生，非模拟。"""

    area: str
    student_count: int
    avg_mastery: Optional[float] = None


class InsightConfirmRequest(BaseModel):
    """教师确认诊断请求体；teacher_note 留痕人工诊断依据。"""

    teacher_note: Optional[str] = None


class ProjectLearningInsightOut(BaseModel):
    """项目学情诊断响应：聚合来源、快照与确认状态。"""

    id: str
    project_id: str
    status: str  # draft / insufficient_evidence / confirmed / stale
    segments: list[InsightSegment] = []
    overall_mastery: Optional[float] = None
    weak_points: list[InsightWeakPoint] = []
    teaching_suggestions: list[str] = []
    source_counts: InsightSourceCounts
    evidence_cutoff: Optional[datetime] = None
    generated_at: Optional[datetime] = None
    generated_by: Optional[str] = None
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    teacher_note: Optional[str] = None
    is_current: bool = True
