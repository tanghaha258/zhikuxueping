from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.tasks import service
from app.schemas.task import (
    TaskAssignmentRequest,
    TaskAssignmentResponse,
    TaskCreate,
    TaskDependencyCreate,
    TaskDependencyResponse,
    TaskResponse,
    TaskTransitionRequest,
    TaskUpdate,
)


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/stats")
def task_stats_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    return success_response(data=service.get_teacher_stats(db, current_user))


@router.get("/center", summary="跨项目任务中心")
def task_center_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """跨项目任务中心（Task 9）：聚合当前教师可管理项目的任务，按待办分类桶组织。"""
    return success_response(data=service.get_task_center(db, current_user).model_dump())


@router.get("")
def list_tasks_api(
    project_id: str = Query(""),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    stage: str = Query("", description="按教学阶段过滤: pre_class/in_class/post_class"),
    tier: str = Query("", description="按分层对象过滤: foundation/enhancement/extension"),
    publish_status: str = Query("", description="按发布状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not project_id:
        raise AppException(code=40001, message="project_id is required", status_code=400)
    try:
        items = service.list_tasks_by_project(
            db, current_user, project_id, skip, limit,
            stage=stage or None,
            tier=tier or None,
            publish_status=publish_status or None,
        )
        total = service.count_tasks_by_project(
            db, current_user, project_id,
            stage=stage or None,
            tier=tier or None,
            publish_status=publish_status or None,
        )
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data={"items": [_task_response(task) for task in items], "total": total})


@router.post("")
def create_task_api(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        task = service.create_task(db, current_user, data)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_task_response(task), message="created")


@router.get("/my")
def my_tasks_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student", "parent"])),
):
    return success_response(data=[_task_response(task) for task in service.list_my_tasks(db, current_user)])


@router.get("/{task_id}")
def get_task_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task = service.get_task(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_task_response(task))


@router.put("/{task_id}")
def update_task_api(
    task_id: str,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        task = service.update_task(db, current_user, task_id, data)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_task_response(task), message="updated")


@router.delete("/{task_id}")
def delete_task_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        service.delete_task(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(message="deleted")


@router.get("/{task_id}/assignments")
def list_assignments_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        items = service.list_assignments(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=[TaskAssignmentResponse.model_validate(item) for item in items])


@router.post("/{task_id}/assignments", summary="设置任务分配学生（整体替换）")
def set_assignments_api(
    task_id: str,
    data: TaskAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """整体替换任务分配学生（Task 1）：去重、逐一校验、原子写入。

    非法学生 ID 整体拒绝（422），不产生部分写入。
    """
    try:
        items = service.set_assignments(db, current_user, task_id, data.student_ids)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(
        data=[TaskAssignmentResponse.model_validate(item) for item in items],
        message="updated",
    )


@router.post("/{task_id}/publish")
def publish_task_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        task = service.publish_task(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40001, message=str(error), status_code=400) from error
    return success_response(data=_task_response(task), message="published")


@router.post("/{task_id}/close")
def close_task_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        task = service.close_task(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40001, message=str(error), status_code=400) from error
    return success_response(data=_task_response(task), message="closed")


# ── 核心闭环扩展：依赖管理 ──────────────────────────────────
@router.post("/{task_id}/dependencies", summary="Add task dependency")
def add_dependency_api(
    task_id: str,
    data: TaskDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """添加任务依赖：predecessor 完成后 successor（路径 task_id）才可开始。

    校验：自环→400，前置不存在→404，跨项目→400，重复→409，环→409，日期冲突→400。
    """
    try:
        dependency = service.add_dependency(db, current_user, task_id, data.predecessor_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(
        data=TaskDependencyResponse.model_validate(dependency).model_dump(),
        message="created",
    )


@router.delete("/{task_id}/dependencies/{predecessor_id}", summary="Remove task dependency")
def remove_dependency_api(
    task_id: str,
    predecessor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        service.remove_dependency(db, current_user, task_id, predecessor_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(message="deleted")


@router.get("/{task_id}/dependencies", summary="List task dependencies")
def list_dependencies_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回任务的直接前驱与后继列表。"""
    try:
        result = service.list_dependencies(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=result.model_dump())


# ── 核心闭环扩展：发布状态机 ────────────────────────────────
@router.post("/{task_id}/transition", summary="Transition task publish status")
def transition_api(
    task_id: str,
    data: TaskTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """任务发布状态机迁移（计划 4.3）。非法跃迁返回 409。"""
    try:
        task = service.transition_publish_status(db, current_user, task_id, data)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_task_response(task), message="transitioned")


@router.get("/{task_id}/publish-preview", summary="Task publish preview")
def publish_preview_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发布预览（计划 3.5.4）：不改变状态，返回将发布给学生的快照。"""
    try:
        preview = service.publish_preview(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=preview.model_dump())


@router.get("/{task_id}/progress", summary="Task execution progress")
def task_progress_api(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """任务执行进度汇总（Task 9）：从分配与提交聚合，不读取 task.status。"""
    try:
        progress = service.get_task_progress(db, current_user, task_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=progress.model_dump())


def _task_response(task) -> dict:
    return TaskResponse.model_validate(task).model_dump()
