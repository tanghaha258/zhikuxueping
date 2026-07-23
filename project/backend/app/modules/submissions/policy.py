"""提交领域权限策略（Task 6 扩展）。

学生可见性与敏感信息隐藏：
- 学生只能查看自己的提交，不能查看他人提交。
- 学生不能看到教师私有备注（teacher_private_note）。
- 学生只能访问自己班级被分配的项目，不能跨班级/跨项目访问。
- 分层资源授权：仅 PUBLISHED 资源对学生可见，按 tier 分组友好展示。
- 未发布评价（status != PUBLISHED/FINALIZED）不可见。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import EvaluationStatus, ReviewStatus
from app.models.project import Project, ProjectClass
from app.models.resource import Resource
from app.models.submission import Submission
from app.models.task import Task
from app.models.user import Role, User
from app.modules.tasks.policy import ensure_can_manage_task, ensure_can_read_task


def ensure_can_submit_to_task(db: Session, actor: User, task_id: str) -> None:
    task, project, class_ids = _task_context(db, task_id)
    if actor.role != Role.STUDENT:
        raise AppException(code=40301, message="permission denied", status_code=403)
    if not class_ids:
        return
    ensure_can_read_task(actor, project, class_ids)


def ensure_can_read_submission(
    db: Session,
    actor: User,
    submission: Submission,
) -> None:
    task, project, class_ids = _task_context(db, submission.task_id)
    if actor.role == Role.STUDENT and actor.id != submission.student_id:
        raise AppException(code=40301, message="permission denied", status_code=403)
    if actor.role == Role.STUDENT and not class_ids:
        return
    ensure_can_read_task(actor, project, class_ids)


def ensure_can_manage_submission(
    db: Session,
    actor: User,
    submission: Submission,
) -> None:
    ensure_can_manage_task_submissions(db, actor, submission.task_id)


def ensure_can_manage_task_submissions(
    db: Session,
    actor: User,
    task_id: str,
) -> None:
    task, project, class_ids = _task_context(db, task_id)
    ensure_can_manage_task(actor, project, class_ids)


def _task_context(db: Session, task_id: str) -> tuple[Task, Project, list[str]]:
    task = db.get(Task, task_id)
    if not task:
        raise AppException(code=40401, message="task not found", status_code=404)
    project = db.get(Project, task.project_id)
    if not project:
        raise AppException(code=40401, message="project not found", status_code=404)
    statement = select(ProjectClass.class_id).where(ProjectClass.project_id == project.id)
    class_ids = list(db.execute(statement).scalars().all())
    return task, project, class_ids


# ============================================================
# Task 6 新增：学生可见性与敏感信息隐藏
# ============================================================

def ensure_student_can_read_project(
    db: Session,
    actor: User,
    project_id: str,
) -> Project:
    """学生只能访问自己班级被明确分配的项目（计划 3.7.2）。"""
    if actor.role != Role.STUDENT:
        # 非学生角色走原有项目权限链
        project = db.get(Project, project_id)
        if not project:
            raise AppException(code=40401, message="项目不存在", status_code=404)
        class_ids = list(
            db.execute(
                select(ProjectClass.class_id).where(
                    ProjectClass.project_id == project_id
                )
            ).scalars().all()
        )
        ensure_can_read_task(actor, project, class_ids)
        return project

    project = db.get(Project, project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)

    # 学生必须有所属班级且班级被分配到该项目
    if not actor.class_id:
        raise AppException(
            code=40301, message="无权访问该项目（未分配班级）", status_code=403
        )
    assigned = db.execute(
        select(ProjectClass).where(
            ProjectClass.project_id == project_id,
            ProjectClass.class_id == actor.class_id,
        )
    ).scalar_one_or_none()
    if not assigned:
        raise AppException(
            code=40301, message="无权访问该项目", status_code=403
        )
    return project


def ensure_student_can_read_submission(
    db: Session,
    actor: User,
    submission: Submission,
) -> None:
    """学生只能查看自己的提交（计划 3.7.2/7.2 越权拒绝）。"""
    if actor.role == Role.STUDENT:
        if actor.id != submission.student_id:
            raise AppException(
                code=40301, message="不能查看他人提交", status_code=403
            )
        return
    # 非学生走标准读取权限
    ensure_can_read_submission(db, actor, submission)


def ensure_can_resubmit(actor: User, submission: Submission) -> None:
    """只有提交所有者学生本人可以再提交/发起二次评价。"""
    if actor.role != Role.STUDENT:
        raise AppException(code=40301, message="仅学生可再提交", status_code=403)
    if actor.id != submission.student_id:
        raise AppException(
            code=40301, message="只能对自己的提交进行再提交", status_code=403
        )


def filter_student_resources(resources: list[Resource]) -> list[Resource]:
    """学生可见资源：仅 PUBLISHED，过滤未发布/草稿/退回资源。"""
    return [
        r for r in resources
        if r.review_status == ReviewStatus.PUBLISHED
    ]


def hide_submission_sensitive_fields(
    submission: Submission,
    actor: User,
) -> dict:
    """序列化提交给学生时隐藏敏感字段（教师私有备注不暴露）。

    教师视角返回完整字段；学生视角隐藏 teacher_private_note。
    """
    data = {
        "id": submission.id,
        "task_id": submission.task_id,
        "student_id": submission.student_id,
        "content": submission.content,
        "file_urls": submission.file_urls,
        "status": submission.status,
        "review_status": submission.review_status.value,
        "score": submission.score,
        "comment": submission.comment,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
    }
    # 学生视角不返回教师私有备注（旧 Submission 模型无此字段，
    # 但 SubmissionRevision 有；此处仅做 Submission 层级过滤，
    # 版本层级在 service._revision_student_dict 中已隐藏）
    if actor.role == Role.STUDENT:
        data.pop("teacher_private_note", None)
    return data


def ensure_feedback_published(record_status: EvaluationStatus) -> None:
    """未发布评价不可见（计划 3.7.4 验收）。"""
    if record_status not in {EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED}:
        raise AppException(
            code=40301, message="评价尚未发布，暂不可见", status_code=403
        )
