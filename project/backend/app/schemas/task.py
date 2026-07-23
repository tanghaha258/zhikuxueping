from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    project_id: str
    title: str
    description: Optional[str] = None
    task_type: str = "individual"
    max_score: int = 100
    deadline: Optional[datetime] = None
    rubric: Optional[str] = None
    student_ids: list[str] = []
    # 核心闭环扩展（计划 4.1）
    stage: Optional[str] = None
    tier: Optional[str] = None
    submission_type: Optional[str] = None
    max_attempts: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    max_score: Optional[int] = None
    deadline: Optional[datetime] = None
    rubric: Optional[str] = None
    # 核心闭环扩展（publish_status 不在此直接设置，由 /transition 端点强制状态机）
    stage: Optional[str] = None
    tier: Optional[str] = None
    submission_type: Optional[str] = None
    max_attempts: Optional[int] = None
    scheduled_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str] = None
    task_type: str
    status: str
    max_score: int
    deadline: Optional[datetime] = None
    rubric: Optional[str] = None
    created_by: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 核心闭环扩展字段（历史任务为 NULL/PUBLISHED，向后兼容）
    stage: Optional[str] = None
    tier: Optional[str] = None
    publish_status: Optional[str] = None
    submission_type: Optional[str] = None
    max_attempts: Optional[int] = None
    scheduled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskAssignmentResponse(BaseModel):
    id: str
    task_id: str
    student_id: str
    assigned_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskAssignmentRequest(BaseModel):
    """设置任务分配学生（Task 1）：整体替换式写入，去重并逐一校验。"""

    student_ids: list[str]


class TaskDependencyCreate(BaseModel):
    """添加任务依赖：predecessor 完成后 successor 才可开始。

    在 `POST /tasks/{successor_id}/dependencies` 中，`predecessor_id` 为前置任务，
    路径中的 task 即为后置任务（successor）。
    """

    predecessor_id: str


class TaskDependencyResponse(BaseModel):
    id: str
    predecessor_id: str
    successor_id: str
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskDependencyListResponse(BaseModel):
    """任务的直接前驱与后继列表。"""

    predecessors: list[TaskDependencyResponse]
    successors: list[TaskDependencyResponse]


class TaskTransitionRequest(BaseModel):
    """任务发布状态机迁移请求。

    target 取值：scheduled / published / in_progress / closed / archived。
    非法跃迁返回 409。scheduled 可携带 scheduled_at（定时发布）。
    """

    target: str
    scheduled_at: Optional[datetime] = None


class TaskPublishPreview(BaseModel):
    """发布预览（计划 3.5.4）：不改变状态，返回将发布给学生的快照。"""

    task: "TaskResponse"
    assigned_students: list[str]
    resources: list[dict]
    dependencies_ready: bool
    blockers: list[str]
    warnings: list[str]


# 前向引用解析
TaskPublishPreview.model_rebuild()
