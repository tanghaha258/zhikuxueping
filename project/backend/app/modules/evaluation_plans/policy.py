"""评价计划领域权限策略（计划 Task 4）。

复用 `app.modules.projects.policy` 的可见性与管理权限判断，
保证跨教师、跨学校、跨班级的访问规则与项目主表一致。

学生权限（验收标准）：
- 学生不可见未发布评价（status < PUBLISHED）
- 学生不可见他人评价（student_id != actor.id 时 403）
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.models.evaluation_plan import EvaluationRecord
from app.models.enums import EvaluationStatus
from app.models.project import Project
from app.models.user import Role, User
from app.modules.projects.policy import (
    ensure_can_manage,
    ensure_can_read,
)

# 学生可见的评价状态：已发布及之后的状态
_STUDENT_VISIBLE_STATUSES = {
    EvaluationStatus.PUBLISHED,
    EvaluationStatus.APPEALED,
    EvaluationStatus.RECHECKED,
    EvaluationStatus.FINALIZED,
}


def ensure_can_read_plan(actor: User, project: Project, class_ids: list[str]) -> None:
    """读取评价计划：与项目读取权限一致。"""
    ensure_can_read(actor, project, class_ids)


def ensure_can_manage_plan(actor: User, project: Project, class_ids: list[str]) -> None:
    """管理评价计划（量规/维度/证据）：与项目管理权限一致。"""
    ensure_can_manage(actor, project, class_ids)


def ensure_plan_editable(actor: User, project: Project, class_ids: list[str]) -> None:
    """量规/维度编辑：仅在项目处于 draft/pending_review/returned 状态允许。

    正式（active 及之后）项目的量规进入只读，需新建版本。
    评价记录的状态机迁移（确认/发布）不受此限制，在 active 后仍可用。
    """
    ensure_can_manage_plan(actor, project, class_ids)
    editable_statuses = {"draft", "pending_review", "returned"}
    current = project.status.value if hasattr(project.status, "value") else str(project.status)
    if current not in editable_statuses:
        raise AppException(
            code=40901,
            message=f"当前项目状态 {current} 不允许编辑评价计划，请新建量规版本",
            status_code=409,
        )


def ensure_can_manage_record(
    actor: User, project: Project, class_ids: list[str]
) -> None:
    """评价记录管理（创建/状态迁移/确认）：与项目管理权限一致，不限项目状态。

    评价记录在项目 active 后才进入实际流转，因此不施加状态限制，
    仅校验权限。
    """
    ensure_can_manage(actor, project, class_ids)


def ensure_student_can_read_record(
    actor: User, record: EvaluationRecord, project: Project, class_ids: list[str]
) -> None:
    """学生读取评价记录：只能看自己且状态已发布。

    验收：学生不可见未发布评价、不可见他人评价。
    """
    # 教师和管理员可读取任意记录
    if actor.role in {Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER}:
        ensure_can_read(actor, project, class_ids)
        return
    # 学生：必须通过班级归属访问项目
    ensure_can_read(actor, project, class_ids)
    if actor.id != record.student_id:
        raise AppException(code=40301, message="不能查看他人评价", status_code=403)
    current = record.status.value if hasattr(record.status, "value") else str(record.status)
    try:
        status_enum = EvaluationStatus(current)
    except ValueError:
        raise AppException(code=40301, message="评价状态异常", status_code=403)
    if status_enum not in _STUDENT_VISIBLE_STATUSES:
        raise AppException(code=40301, message="评价未发布，暂不可见", status_code=403)
