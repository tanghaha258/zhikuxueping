from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.evaluation import EvaluationCreate, EvaluationUpdate, EvaluationResponse
from app.modules.evaluations.service import (
    create_evaluation, update_evaluation, list_evaluations_by_task,
    list_evaluations_by_student, get_evaluation,
)
from app.modules.evaluations.policy import (
    can_read_evaluation,
    ensure_can_manage_evaluation,
    ensure_can_manage_task_evaluations,
    ensure_can_read_evaluation,
    ensure_can_read_task_evaluations,
)

router = APIRouter(prefix="/evaluations", tags=["多元评价"])

_LEGACY_WRITE_DEPRECATED_MESSAGE = (
    "旧版评价写入入口已弃用，请使用 /api/v1/evaluation-plans/records 创建 EvaluationRecord"
)


@router.post("", summary="创建评价（已弃用）")
def create_evaluation_api(data: EvaluationCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["teacher", "school_admin"]))):
    """旧写入入口已下线：调用即返回 410，不写入旧 `Evaluation` 表。

    新评价请使用 `POST /api/v1/evaluation-plans/records` 创建 `EvaluationRecord`，
    走状态机（DRAFT -> COLLECTING_EVIDENCE -> PENDING_TEACHER_CONFIRMATION
    -> CONFIRMED -> PUBLISHED）与教师确认流程。
    """
    raise AppException(
        code=41001,
        message=_LEGACY_WRITE_DEPRECATED_MESSAGE,
        status_code=410,
    )


@router.get("/task/{task_id}", summary="任务的评价列表（只读历史）")
def task_evaluations_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_can_read_task_evaluations(db, current_user, task_id)
    items = list_evaluations_by_task(db, task_id)
    if current_user.role == "student":
        items = [item for item in items if item.student_id == current_user.id]
    return success_response(data=[EvaluationResponse.model_validate(e) for e in items])


@router.get("/student/{student_id}", summary="学生的评价列表（只读历史）")
def student_evaluations_api(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = list_evaluations_by_student(db, student_id)
    items = [item for item in items if can_read_evaluation(db, current_user, item)]
    return success_response(data=[EvaluationResponse.model_validate(e) for e in items])


@router.get("/{evaluation_id}", summary="评价详情（只读历史）")
def get_evaluation_api(
    evaluation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    eval_obj = get_evaluation(db, evaluation_id)
    if not eval_obj:
        raise AppException(code=40401, message="评价不存在", status_code=404)
    ensure_can_read_evaluation(db, current_user, eval_obj)
    return success_response(data=EvaluationResponse.model_validate(eval_obj))


@router.put("/{evaluation_id}", summary="更新评价（已弃用）")
def update_evaluation_api(evaluation_id: str, data: EvaluationUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["teacher", "school_admin"]))):
    """旧更新入口已下线：旧版评价记录不可修改，保留为只读历史数据。

    如需修订评价，请新建 `EvaluationRecord` 版本（状态机迁移至 PUBLISHED）。
    """
    raise AppException(
        code=41001,
        message=_LEGACY_WRITE_DEPRECATED_MESSAGE,
        status_code=410,
    )
