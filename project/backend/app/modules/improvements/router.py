"""学情改进领域 API 路由（计划 Task 7）。

端点前缀：/api/v1/improvements

覆盖：
- 改进建议列表、创建、详情
- 建议采用/修改/拒绝（留痕）
- 建议转任务/测评（可发布为正式 Task）
- 二次评价创建与对比
- 改进任务列表与二次评价列表

设计要点：
- 建议必须引用评价证据（无证据抛 400，不生成确定性学生标签）。
- 教师决定必须留痕原因；状态机非法跃迁返回 409。
- 改进任务与二次评价均可追溯到原评价 ID。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.enums import (
    ImprovementSuggestionStatus,
    ImprovementTaskType,
)
from app.models.user import User
from app.modules.improvements import service
from app.schemas.improvement import (
    ImprovementSuggestionCreate,
    ImprovementTaskCreate,
    SecondEvaluationCreate,
    SuggestionDecisionRequest,
)

router = APIRouter(prefix="/improvements", tags=["学情改进"])


# ── 改进建议 ──────────────────────────────────────────────────
@router.get("/suggestions", summary="改进建议列表")
def list_suggestions_api(
    project_id: str = Query(..., description="项目 ID"),
    student_id: str | None = Query(None, description="按学生过滤"),
    status: ImprovementSuggestionStatus | None = Query(
        None, description="按状态过滤"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_suggestions(
        db,
        current_user,
        project_id=project_id,
        student_id=student_id,
        status=status,
    )
    return success_response(
        {
            "items": [service.suggestion_dict(s) for s in items],
            "total": len(items),
        }
    )


@router.post("/suggestions", summary="创建改进建议（必须引用评价证据）")
def create_suggestion_api(
    data: ImprovementSuggestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = service.create_suggestion(db, current_user, data)
    return success_response(service.suggestion_dict(suggestion))


@router.get("/suggestions/{suggestion_id}", summary="改进建议详情")
def get_suggestion_api(
    suggestion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = service.get_suggestion_detail(db, current_user, suggestion_id)
    return success_response(service.suggestion_dict(suggestion))


@router.post("/suggestions/{suggestion_id}/decision", summary="采用/修改/拒绝建议（留痕）")
def decide_suggestion_api(
    suggestion_id: str,
    data: SuggestionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = service.decide_suggestion(
        db, current_user, suggestion_id, data
    )
    return success_response(service.suggestion_dict(suggestion))


# ── 改进任务（建议转任务/测评）────────────────────────────────
@router.post("/tasks", summary="建议转任务/测评（可发布为正式 Task）")
def create_improvement_task_api(
    data: ImprovementTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = service.create_improvement_task(db, current_user, data)
    return success_response(service.improvement_task_dict(task))


@router.get("/tasks", summary="改进任务列表")
def list_improvement_tasks_api(
    project_id: str = Query(..., description="项目 ID"),
    task_type: ImprovementTaskType | None = Query(
        None, description="按任务类型过滤"
    ),
    link_suggestion_id: str | None = Query(
        None, description="按关联建议过滤"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_improvement_tasks(
        db,
        current_user,
        project_id=project_id,
        task_type=task_type,
        link_suggestion_id=link_suggestion_id,
    )
    return success_response(
        {
            "items": [service.improvement_task_dict(t) for t in items],
            "total": len(items),
        }
    )


# ── 二次评价 ──────────────────────────────────────────────────
@router.post("/second-evaluations", summary="创建二次评价（前后对比）")
def create_second_evaluation_api(
    data: SecondEvaluationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    evaluation = service.create_second_evaluation(db, current_user, data)
    return success_response(service.second_evaluation_dict(evaluation))


@router.get("/second-evaluations", summary="二次评价列表")
def list_second_evaluations_api(
    project_id: str = Query(..., description="项目 ID"),
    student_id: str | None = Query(None, description="按学生过滤"),
    link_suggestion_id: str | None = Query(
        None, description="按关联建议过滤"
    ),
    link_improvement_task_id: str | None = Query(
        None, description="按关联改进任务过滤"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_second_evaluations(
        db,
        current_user,
        project_id=project_id,
        student_id=student_id,
        link_suggestion_id=link_suggestion_id,
        link_improvement_task_id=link_improvement_task_id,
    )
    return success_response(
        {
            "items": [service.second_evaluation_dict(e) for e in items],
            "total": len(items),
        }
    )
