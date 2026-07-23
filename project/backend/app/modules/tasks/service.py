"""任务服务层。

核心闭环扩展（计划 4.1/3.5/3.7）：
- `create_task`/`update_task` 支持 stage/tier/submission_type/max_attempts/scheduled_at。
- 依赖管理：`add_dependency`（自环/重复/环/日期冲突校验）、`remove_dependency`、`list_dependencies`。
- `transition_publish_status`：发布状态机迁移，非法跃迁返回 409。
- `publish_preview`：发布预览快照，不改变状态。
- `list_my_tasks`：学生侧仅返回 PUBLISHED/IN_PROGRESS 任务。

双状态轴说明：
- `Task.status`：学生侧执行进度（pending/in_progress/submitted/evaluated），
  由现有 `publish_task`/`close_task` 操作，保留不变。
- `Task.publish_status`：发布生命周期（draft/scheduled/published/in_progress/closed/archived），
  由 `transition_publish_status` 操作，描述对学生可见性。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import (
    ResourceTier,
    SubmissionType,
    TaskPublishStatus,
    TeachingStage,
)
from app.models.task import Task, TaskStatus
from app.models.task_dependency import TaskDependency
from app.models.user import Role, User
from app.modules.projects.service import is_student_assignable_to_project
from app.modules.resources.repository import ResourceRepository
from app.modules.tasks.policy import ensure_can_manage_task, ensure_can_read_task
from app.modules.tasks.repository import TaskRepository
from app.schemas.task import (
    TaskCreate,
    TaskDependencyListResponse,
    TaskDependencyResponse,
    TaskPublishPreview,
    TaskResponse,
    TaskTransitionRequest,
    TaskUpdate,
)


# 学生可见的任务发布状态（计划 3.7）：仅已发布/进行中任务对学生可见。
_STUDENT_VISIBLE_PUBLISH = {TaskPublishStatus.PUBLISHED, TaskPublishStatus.IN_PROGRESS}


# ── 发布状态机（计划 4.3）──────────────────────────────────
# 允许的迁移：当前状态 → {可到达的状态集合}。
_PUBLISH_TRANSITIONS: dict[TaskPublishStatus, set[TaskPublishStatus]] = {
    TaskPublishStatus.DRAFT: {TaskPublishStatus.SCHEDULED, TaskPublishStatus.PUBLISHED},
    TaskPublishStatus.SCHEDULED: {TaskPublishStatus.PUBLISHED, TaskPublishStatus.DRAFT},
    TaskPublishStatus.PUBLISHED: {
        TaskPublishStatus.IN_PROGRESS,
        TaskPublishStatus.CLOSED,
        TaskPublishStatus.ARCHIVED,
    },
    TaskPublishStatus.IN_PROGRESS: {
        TaskPublishStatus.CLOSED,
        TaskPublishStatus.ARCHIVED,
    },
    TaskPublishStatus.CLOSED: {TaskPublishStatus.ARCHIVED},
    TaskPublishStatus.ARCHIVED: set(),
}


def create_task(db: Session, actor: User, data: TaskCreate) -> Task:
    repository = TaskRepository(db)
    project, class_ids = _project_context(repository, data.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    _validate_student_ids(db, data.project_id, data.student_ids)
    task = Task(
        project_id=data.project_id,
        title=data.title,
        description=data.description,
        task_type=data.task_type,
        max_score=data.max_score,
        deadline=data.deadline,
        rubric=data.rubric,
        created_by=actor.id,
        stage=_parse_stage(data.stage),
        tier=_parse_tier(data.tier),
        submission_type=_parse_submission_type(data.submission_type),
        max_attempts=data.max_attempts,
        scheduled_at=data.scheduled_at,
    )
    repository.add(task)
    db.flush()
    repository.add_assignments(task.id, data.student_ids)
    return _commit_and_refresh(db, task)


def get_task(db: Session, actor: User, task_id: str) -> Task:
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_read_task(actor, project, class_ids)
    # 学生仅可见已发布/进行中任务（计划 3.7）
    if actor.role == Role.STUDENT and task.publish_status not in _STUDENT_VISIBLE_PUBLISH:
        raise AppException(code=40301, message="任务尚未发布，无权访问", status_code=403)
    return task


def list_tasks_by_project(
    db: Session,
    actor: User,
    project_id: str,
    skip: int = 0,
    limit: int = 100,
    *,
    stage: str | None = None,
    tier: str | None = None,
    publish_status: str | None = None,
) -> list[Task]:
    repository = TaskRepository(db)
    project, class_ids = _project_context(repository, project_id)
    ensure_can_read_task(actor, project, class_ids)
    return repository.list_by_project(
        project_id, skip, limit, stage=stage, tier=tier, publish_status=publish_status
    )


def count_tasks_by_project(
    db: Session,
    actor: User,
    project_id: str,
    *,
    stage: str | None = None,
    tier: str | None = None,
    publish_status: str | None = None,
) -> int:
    repository = TaskRepository(db)
    project, class_ids = _project_context(repository, project_id)
    ensure_can_read_task(actor, project, class_ids)
    return repository.count_by_project(
        project_id, stage=stage, tier=tier, publish_status=publish_status
    )


def update_task(db: Session, actor: User, task_id: str, data: TaskUpdate) -> Task:
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    updates = data.model_dump(exclude_unset=True)
    # 枚举字段需转换；publish_status 不在此设置，由 /transition 端点强制状态机。
    if "stage" in updates:
        task.stage = _parse_stage(updates.pop("stage"))
    if "tier" in updates:
        task.tier = _parse_tier(updates.pop("tier"))
    if "submission_type" in updates:
        task.submission_type = _parse_submission_type(updates.pop("submission_type"))
    if "status" in updates:
        # status 仍允许通过 update 修改（保持向后兼容），但需校验枚举值
        task.status = _parse_task_status(updates.pop("status"))
    for field, value in updates.items():
        setattr(task, field, value)
    return _commit_and_refresh(db, task)


def delete_task(db: Session, actor: User, task_id: str) -> None:
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    repository.delete_with_dependents(task)
    _commit(db)


def list_assignments(db: Session, actor: User, task_id: str):
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    return repository.list_assignments(task_id)


def set_assignments(db: Session, actor: User, task_id: str, student_ids: list[str]) -> list:
    """整体替换任务分配学生（Task 1）：去重、逐一校验、原子写入。

    非法学生 ID 整体拒绝，不产生部分写入。校验规则：
    - 学生属于项目关联班级
    - 学生处于启用状态
    - 教师对该学生有管理关系（通过项目读权限保证）
    """
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    _validate_student_ids(db, task.project_id, student_ids)
    # 去重后写入
    seen: set[str] = set()
    unique_ids = [sid for sid in student_ids if not (sid in seen or seen.add(sid))]
    repository.replace_assignments(task_id, unique_ids)
    _commit(db)
    return repository.list_assignments(task_id)


def list_my_tasks(db: Session, actor: User) -> list[Task]:
    """学生侧任务列表：仅返回已发布/进行中任务（计划 3.7）。"""
    return TaskRepository(db).list_for_student(actor.id, actor.class_id, published_only=True)


def publish_task(db: Session, actor: User, task_id: str) -> Task:
    """现有发布端点：操作 Task.status（PENDING→IN_PROGRESS），保留向后兼容。"""
    return _change_status(db, actor, task_id, TaskStatus.PENDING, TaskStatus.IN_PROGRESS, "发布")


def close_task(db: Session, actor: User, task_id: str) -> Task:
    """现有关闭端点：操作 Task.status（IN_PROGRESS→EVALUATED），保留向后兼容。"""
    return _change_status(db, actor, task_id, TaskStatus.IN_PROGRESS, TaskStatus.EVALUATED, "关闭")


def get_teacher_stats(db: Session, actor: User) -> dict:
    return TaskRepository(db).teacher_stats(actor.id)


# ── 依赖管理 ───────────────────────────────────────────────
def add_dependency(
    db: Session, actor: User, successor_id: str, predecessor_id: str
) -> TaskDependency:
    """添加任务依赖：predecessor 完成后 successor 才可开始。

    校验（计划 3.5.4）：
    - 自环：successor == predecessor → 400
    - 前置不存在 → 404
    - 前置与后置不属于同一项目 → 400
    - 重复登记 → 409
    - 环检测：添加后存在环 → 409
    - 日期冲突：successor.deadline < predecessor.deadline → 400
    """
    repository = TaskRepository(db)
    successor = _require_task(repository, successor_id)
    project, class_ids = _project_context(repository, successor.project_id)
    ensure_can_manage_task(actor, project, class_ids)

    if successor_id == predecessor_id:
        raise AppException(
            code=40001, message="不能将任务设为自身的前置依赖", status_code=400
        )

    predecessor = repository.get(predecessor_id)
    if not predecessor:
        raise AppException(
            code=40401, message="前置任务不存在", status_code=404
        )
    if predecessor.project_id != successor.project_id:
        raise AppException(
            code=40001,
            message="前置任务与后置任务不属于同一项目",
            status_code=400,
        )

    existing = repository.find_dependency(predecessor_id, successor_id)
    if existing:
        raise AppException(
            code=40901,
            message="该依赖关系已存在",
            status_code=409,
        )

    # 环检测：若 successor 已能到达 predecessor，则添加后会形成环。
    if repository.exists_path(successor_id, predecessor_id):
        raise AppException(
            code=40901,
            message="添加该依赖将形成环，任务链不允许循环依赖",
            status_code=409,
        )

    # 日期冲突：后置任务截止时间不能早于前置任务截止时间。
    if (
        successor.deadline is not None
        and predecessor.deadline is not None
        and successor.deadline < predecessor.deadline
    ):
        raise AppException(
            code=40001,
            message=(
                "后置任务的截止时间不能早于前置任务，"
                f"前置截止 {predecessor.deadline.isoformat()}，"
                f"后置截止 {successor.deadline.isoformat()}"
            ),
            status_code=400,
        )

    dependency = TaskDependency(predecessor_id=predecessor_id, successor_id=successor_id)
    repository.add_dependency(dependency)
    _commit(db)
    db.refresh(dependency)
    return dependency


def remove_dependency(
    db: Session, actor: User, successor_id: str, predecessor_id: str
) -> None:
    repository = TaskRepository(db)
    successor = _require_task(repository, successor_id)
    project, class_ids = _project_context(repository, successor.project_id)
    ensure_can_manage_task(actor, project, class_ids)

    dependency = repository.find_dependency(predecessor_id, successor_id)
    if not dependency:
        raise AppException(
            code=40401, message="未找到指定的依赖关系", status_code=404
        )
    repository.remove_dependency(dependency)
    _commit(db)


def list_dependencies(
    db: Session, actor: User, task_id: str
) -> TaskDependencyListResponse:
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_read_task(actor, project, class_ids)
    predecessors = [
        TaskDependencyResponse.model_validate(d) for d in repository.list_predecessors(task_id)
    ]
    successors = [
        TaskDependencyResponse.model_validate(d) for d in repository.list_successors(task_id)
    ]
    return TaskDependencyListResponse(predecessors=predecessors, successors=successors)


# ── 发布状态机 ─────────────────────────────────────────────
def transition_publish_status(
    db: Session, actor: User, task_id: str, request: TaskTransitionRequest
) -> Task:
    """任务发布状态机迁移（计划 4.3）。

    非法跃迁返回 409。SCHEDULED 可携带 scheduled_at；PUBLISHED 时清空 scheduled_at。
    """
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)

    target = _parse_publish_status(request.target)
    current = task.publish_status
    if target not in _PUBLISH_TRANSITIONS.get(current, set()):
        raise AppException(
            code=40901,
            message=(
                f"发布状态不允许从 {current.value} 迁移到 {target.value}，"
                f"当前状态可迁移到: {sorted(t.value for t in _PUBLISH_TRANSITIONS.get(current, set()))}"
            ),
            status_code=409,
        )

    # 发布阻断（Task 1）：未分配学生不得发布，返回 422。
    if target == TaskPublishStatus.PUBLISHED:
        assigned = repository.list_assignment_student_ids(task_id)
        if not assigned:
            raise AppException(
                code=42201,
                message="至少分配一名学生后才能发布任务",
                status_code=422,
            )

    task.publish_status = target
    if target == TaskPublishStatus.SCHEDULED:
        task.scheduled_at = request.scheduled_at
    elif target == TaskPublishStatus.PUBLISHED:
        # 发布时清空定时，立即生效
        task.scheduled_at = None
    return _commit_and_refresh(db, task)


def publish_preview(db: Session, actor: User, task_id: str) -> TaskPublishPreview:
    """发布预览（计划 3.5.4）：不改变状态，返回将发布给学生的快照。

    - `assigned_students`：已分配学生 ID 列表。
    - `resources`：同 project_id + stage + tier 的已发布资源。
    - `dependencies_ready`：所有前置任务是否已 EVALUATED（或无前置）。
    - `blockers`：阻断发布的硬性条件（当前状态不可发布等）。
    - `warnings`：建议处理的非阻断问题（无学生/无资源/前置未就绪）。
    """
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_read_task(actor, project, class_ids)

    assigned_students = repository.list_assignment_student_ids(task_id)

    # 关联资源：同项目同 stage+tier 的已发布资源（计划 4.1 可查询关系）
    stage_val = task.stage.value if task.stage else None
    tier_val = task.tier.value if task.tier else None
    resources = ResourceRepository(db).list_published_by_stage_tier(
        task.project_id, stage_val, tier_val
    )
    resources_payload = [
        {
            "id": r.id,
            "title": r.title,
            "tier": r.tier.value if r.tier else None,
            "stage": r.stage.value if r.stage else None,
            "review_status": r.review_status.value,
        }
        for r in resources
    ]

    # 前置任务就绪检查：所有前置任务 status 为 EVALUATED 视为完成
    predecessor_deps = repository.list_predecessors(task_id)
    predecessors_ready = True
    pending_predecessors: list[str] = []
    for dep in predecessor_deps:
        pred = repository.get(dep.predecessor_id)
        if pred is None or pred.status != TaskStatus.EVALUATED:
            predecessors_ready = False
            pending_predecessors.append(
                pred.title if pred else dep.predecessor_id
            )
    dependencies_ready = predecessors_ready

    blockers: list[str] = []
    warnings: list[str] = []

    # 状态阻断：已发布/进行中/已关闭/已归档的任务不可再次发布
    if task.publish_status not in (
        TaskPublishStatus.DRAFT,
        TaskPublishStatus.SCHEDULED,
    ):
        blockers.append(
            f"任务当前发布状态为 {task.publish_status.value}，仅草稿/定时状态可发布"
        )

    # 发布阻断（Task 1）：无分配学生为硬性阻断，不能发布
    if not assigned_students:
        blockers.append("至少分配一名学生后才能发布任务")

    # 警告：无关联资源
    if not resources_payload:
        warnings.append("未关联已发布资源，学生将看不到对应层级的资源支撑")

    # 警告：前置未就绪
    if predecessor_deps and not predecessors_ready:
        warnings.append(
            "部分前置任务尚未完成（status 非 evaluated）："
            + "、".join(pending_predecessors)
        )

    return TaskPublishPreview(
        task=TaskResponse.model_validate(task),
        assigned_students=assigned_students,
        resources=resources_payload,
        dependencies_ready=dependencies_ready,
        blockers=blockers,
        warnings=warnings,
    )


# ── 内部辅助 ───────────────────────────────────────────────
def _change_status(
    db: Session,
    actor: User,
    task_id: str,
    expected_status: TaskStatus,
    target_status: TaskStatus,
    action_name: str,
) -> Task:
    repository = TaskRepository(db)
    task = _require_task(repository, task_id)
    project, class_ids = _project_context(repository, task.project_id)
    ensure_can_manage_task(actor, project, class_ids)
    if task.status != expected_status:
        raise ValueError(f"任务状态不允许{action_name}，当前状态: {task.status.value}")
    task.status = target_status
    return _commit_and_refresh(db, task)


def _project_context(repository: TaskRepository, project_id: str):
    project = repository.get_project(project_id)
    if not project:
        raise ValueError("project not found")
    return project, repository.project_class_ids(project.id)


def _validate_student_ids(db: Session, project_id: str, student_ids: list[str]) -> None:
    """校验分配学生合法性（Task 1）：去重后逐一校验属于项目关联班级且启用。

    非法 ID 整体拒绝（422），不产生部分写入。
    """
    if not student_ids:
        return
    # 去重并保留顺序
    seen: set[str] = set()
    unique_ids: list[str] = []
    for sid in student_ids:
        if sid in seen:
            continue
        seen.add(sid)
        unique_ids.append(sid)
    invalid: list[str] = []
    for sid in unique_ids:
        if not is_student_assignable_to_project(db, project_id, sid):
            invalid.append(sid)
    if invalid:
        raise AppException(
            code=42201,
            message=(
                "以下学生不属于项目关联班级或已停用，无法分配："
                + "、".join(invalid)
            ),
            status_code=422,
        )


def _require_task(repository: TaskRepository, task_id: str) -> Task:
    task = repository.get(task_id)
    if not task:
        raise ValueError("task not found")
    return task


def _parse_tier(value: str | None) -> ResourceTier | None:
    if value is None or value == "":
        return None
    try:
        return ResourceTier(value)
    except ValueError:
        raise AppException(code=40002, message=f"无效的分层对象: {value}", status_code=400)


def _parse_stage(value: str | None) -> TeachingStage | None:
    if value is None or value == "":
        return None
    try:
        return TeachingStage(value)
    except ValueError:
        raise AppException(code=40002, message=f"无效的教学阶段: {value}", status_code=400)


def _parse_submission_type(value: str | None) -> SubmissionType | None:
    if value is None or value == "":
        return None
    try:
        return SubmissionType(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的提交类型: {value}", status_code=400
        )


def _parse_publish_status(value: str) -> TaskPublishStatus:
    try:
        return TaskPublishStatus(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的发布状态: {value}", status_code=400
        )


def _parse_task_status(value: str) -> TaskStatus:
    try:
        return TaskStatus(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的任务状态: {value}", status_code=400
        )


def _commit_and_refresh(db: Session, task: Task) -> Task:
    _commit(db)
    db.refresh(task)
    return task


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
