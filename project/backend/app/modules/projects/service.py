from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.ai_job import AiJob, QualityIssue
from app.models.enums import (
    EvaluationStatus,
    IssueStatus,
    QualitySeverity,
    SubmissionReviewStatus,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.improvement import SecondEvaluation
from app.models.project import Project, ProjectStatus
from app.models.submission import Submission
from app.models.submission_revision import SubmissionRevision
from app.models.task import Task
from app.models.user import Role, User
from app.modules.project_designs.validators import (
    validate_activation as validate_activation_internal,
)
from app.modules.projects.policy import (
    ensure_can_manage,
    ensure_can_read,
    ensure_can_reopen,
    ensure_not_archived,
    project_visibility_filter,
)
from app.modules.projects.repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


def create_project(db: Session, actor: User, data: ProjectCreate) -> Project:
    repository = ProjectRepository(db)
    project = Project(
        title=data.title,
        description=data.description,
        cover_image_url=data.cover_image_url,
        grade=data.grade,
        start_date=data.start_date,
        end_date=data.end_date,
        creator_id=actor.id,
        school_id=actor.school_id,
    )
    repository.add(project)
    db.flush()
    repository.add_subjects(project.id, data.subject_ids)
    repository.add_classes(project.id, data.class_ids)
    return _commit_and_refresh(db, project)


def get_project(db: Session, actor: User, project_id: str) -> Project:
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_read(actor, project, repository.class_ids(project.id))
    return project


def search_projects(
    db: Session,
    actor: User,
    *,
    keyword: str = "",
    status: str = "",
    grade: str = "",
    creator_id: str = "",
    skip: int = 0,
    limit: int = 20,
) -> list[Project]:
    repository = ProjectRepository(db)
    return repository.list(
        keyword=keyword,
        status=status,
        grade=grade,
        creator_id=creator_id,
        visibility_filter=project_visibility_filter(actor),
        skip=skip,
        limit=limit,
    )


def count_projects(
    db: Session,
    actor: User,
    *,
    keyword: str = "",
    status: str = "",
    grade: str = "",
    creator_id: str = "",
) -> int:
    repository = ProjectRepository(db)
    return repository.count(
        keyword=keyword,
        status=status,
        grade=grade,
        creator_id=creator_id,
        visibility_filter=project_visibility_filter(actor),
    )


def update_project(db: Session, actor: User, project_id: str, data: ProjectUpdate) -> Project:
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_not_archived(project)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    return _commit_and_refresh(db, project)


def delete_project(db: Session, actor: User, project_id: str) -> None:
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_not_archived(project)
    repository.delete_with_dependents(project)
    _commit(db)


def activate_project(db: Session, actor: User, project_id: str) -> Project:
    """激活项目：pending_review -> active，并强制完整性校验。

    依据计划 4.3 状态机：draft -> pending_review -> active。
    直接从 draft 激活被拒绝（409）；从 pending_review 激活时，
    若完整性检查存在 blockers 同样拒绝（409），避免不完整项目进入正式状态。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    if project.status != ProjectStatus.PENDING_REVIEW:
        raise _illegal_transition(
            project.status,
            ProjectStatus.ACTIVE,
            "激活",
            allowed_from=[ProjectStatus.PENDING_REVIEW],
            hint="项目需先提交审核（submit_for_review）后再激活",
        )
    # 服务端强制完整性校验：blockers 非空则拒绝激活。
    validation = validate_activation_internal(db, project)
    if not validation.can_activate:
        raise _blocked_transition(validation.blockers)
    project.status = ProjectStatus.ACTIVE
    return _commit_and_refresh(db, project)


def submit_for_review(db: Session, actor: User, project_id: str) -> Project:
    """提交审核：draft -> pending_review。

    草稿允许暂缺字段（计划 3.4），因此 submit_for_review 不做完整性阻断；
    完整性阻断在 activate 阶段强制。
    """
    return _change_status(
        db, actor, project_id, ProjectStatus.DRAFT, ProjectStatus.PENDING_REVIEW, "提交审核"
    )


def validate_activation(db: Session, actor: User, project_id: str) -> dict:
    """`POST /api/v1/projects/{id}/validate-activation` 服务实现。

    返回 `blockers`、`warnings`、`completion` 和 `details`，
    供前端在激活前展示缺失项与完整度。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_read(actor, project, repository.class_ids(project.id))
    result = validate_activation_internal(db, project)
    return result.to_dict()


def complete_project(db: Session, actor: User, project_id: str) -> Project:
    """完成项目：active -> completed，并强制结项完整性校验。

    依据计划 Task 9 验收：存在未发布反馈或未处理阻断问题时给出明确提示。
    结项前检查：
    - EvaluationRecord.status 不为 PUBLISHED/FINALIZED 的视为未发布反馈，拒绝结项。
    - QualityIssue 中 severity=BLOCKER 且 status=OPEN 的视为未处理阻断问题，拒绝结项。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_not_archived(project)
    if project.status != ProjectStatus.ACTIVE:
        raise _illegal_transition(
            project.status,
            ProjectStatus.COMPLETED,
            "完成",
            allowed_from=[ProjectStatus.ACTIVE],
        )
    _ensure_closure_completeness(db, project.id)
    project.status = ProjectStatus.COMPLETED
    return _commit_and_refresh(db, project)


def archive_project(db: Session, actor: User, project_id: str) -> Project:
    return _change_status(db, actor, project_id, ProjectStatus.COMPLETED, ProjectStatus.ARCHIVED, "归档")


# ============================================================
# 结项/归档扩展（Task 9）
# ============================================================

def reopen_archived_project(
    db: Session, actor: User, project_id: str, reason: str
) -> Project:
    """重新开放归档项目：archived -> active，仅 school_admin 可调用。

    依据计划 Task 9 验收：重新开放必须授权并记录原因。
    - reason 必填且非空，留痕到 project.reopen_reason。
    - 仅 school_admin 角色可调用（ensure_can_reopen）。
    - 状态机：仅 archived 可重新开放；非法跃迁返回 409。
    """
    if not reason or not reason.strip():
        raise AppException(
            code=40001,
            message="重新开放归档项目需填写原因",
            status_code=400,
        )
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_can_reopen(actor, project)
    if project.status != ProjectStatus.ARCHIVED:
        raise _illegal_transition(
            project.status,
            ProjectStatus.ACTIVE,
            "重新开放",
            allowed_from=[ProjectStatus.ARCHIVED],
            hint="仅归档项目可申请重新开放",
        )
    project.status = ProjectStatus.ACTIVE
    project.reopen_reason = reason.strip()
    project.reopened_at = datetime.now(timezone.utc)
    project.reopened_by = actor.id
    return _commit_and_refresh(db, project)


def get_closure_summary(db: Session, actor: User, project_id: str) -> dict:
    """结项数据摘要：学生数/任务数/评价数/订正率/证据完整率/改进效果。

    依据计划 Task 9：返回项目结项时的关键统计，不伪造数据。
    - 学生数：基于提交记录去重统计（实际参与的学生）。
    - 任务数：项目下任务总数。
    - 评价数：项目下 EvaluationRecord 总数。
    - 订正率：有多次订正版本的提交数 / 总提交数。
    - 证据完整率：已确认（confirmed_by 非空）的评价数 / 总评价数。
    - 改进效果：二次评价记录数（SecondEvaluation）。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_read(actor, project, repository.class_ids(project.id))

    # 任务列表
    task_ids = list(
        db.scalars(select(Task.id).where(Task.project_id == project_id)).all()
    )
    task_count = len(task_ids)

    # 学生数（基于提交记录去重）
    student_ids: list[str] = []
    if task_ids:
        student_ids = list(
            db.scalars(
                select(Submission.student_id)
                .where(Submission.task_id.in_(task_ids))
                .distinct()
            ).all()
        )
    student_count = len(student_ids)

    # 评价数
    eval_count = (
        db.scalar(
            select(func.count())
            .select_from(EvaluationRecord)
            .where(EvaluationRecord.project_id == project_id)
        )
        or 0
    )

    # 订正率：有多次 SubmissionRevision 的提交数 / 总提交数
    total_submissions = 0
    revised_submissions = 0
    if task_ids:
        total_submissions = (
            db.scalar(
                select(func.count())
                .select_from(Submission)
                .where(Submission.task_id.in_(task_ids))
            )
            or 0
        )
        if total_submissions > 0:
            submission_ids_subq = select(Submission.id).where(
                Submission.task_id.in_(task_ids)
            )
            revised_subq = (
                select(SubmissionRevision.submission_id)
                .where(SubmissionRevision.submission_id.in_(submission_ids_subq))
                .group_by(SubmissionRevision.submission_id)
                .having(func.count(SubmissionRevision.id) > 1)
            )
            revised_submissions = (
                db.scalar(select(func.count()).select_from(revised_subq.subquery())) or 0
            )
    revision_rate = (
        revised_submissions / total_submissions if total_submissions > 0 else 0.0
    )

    # 证据完整率：已确认评价数 / 总评价数
    confirmed_count = 0
    if eval_count > 0:
        confirmed_count = (
            db.scalar(
                select(func.count())
                .select_from(EvaluationRecord)
                .where(
                    EvaluationRecord.project_id == project_id,
                    EvaluationRecord.confirmed_by.is_not(None),
                )
            )
            or 0
        )
    evidence_completeness_rate = (
        confirmed_count / eval_count if eval_count > 0 else 0.0
    )

    # 改进效果：二次评价记录数
    improvement_count = (
        db.scalar(
            select(func.count())
            .select_from(SecondEvaluation)
            .where(SecondEvaluation.project_id == project_id)
        )
        or 0
    )

    return {
        "project_id": project_id,
        "student_count": student_count,
        "task_count": task_count,
        "evaluation_count": eval_count,
        "revision_rate": round(revision_rate, 4),
        "evidence_completeness_rate": round(evidence_completeness_rate, 4),
        "improvement_effect": {
            "second_evaluation_count": improvement_count,
        },
    }


def save_teacher_reflection(
    db: Session, actor: User, project_id: str, reflection_text: str
) -> Project:
    """保存教师结项反思文本。

    依据计划 Task 9：教师反思存入项目字段（teacher_reflection）。
    归档项目禁止写操作（ensure_not_archived）。
    """
    if not reflection_text or not reflection_text.strip():
        raise AppException(
            code=40001,
            message="反思内容不能为空",
            status_code=400,
        )
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_not_archived(project)
    project.teacher_reflection = reflection_text.strip()
    return _commit_and_refresh(db, project)


def preview_case_anonymization(
    db: Session, actor: User, project_id: str
) -> dict:
    """案例归档脱敏预览：学生姓名→编号、联系方式隐藏。

    依据计划 Task 9：返回脱敏后的案例信息，便于归档与对外分享。
    - 学生姓名替换为 "学生-001"/"学生-002" 等编号。
    - 手机号/邮箱等联系方式不返回（hidden=True）。
    - 保留项目基本信息与每位学生的最新评价分数（无姓名）。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_read(actor, project, repository.class_ids(project.id))

    # 收集项目下所有参与学生：提交记录 + 班级分配
    task_ids_subq = select(Task.id).where(Task.project_id == project_id)
    student_ids: list[str] = list(
        db.scalars(
            select(Submission.student_id)
            .where(Submission.task_id.in_(task_ids_subq))
            .distinct()
        ).all()
    )

    class_ids = repository.class_ids(project_id)
    if class_ids:
        class_student_ids = list(
            db.scalars(
                select(User.id).where(
                    User.class_id.in_(class_ids),
                    User.role == Role.STUDENT,
                )
            ).all()
        )
        seen = set(student_ids)
        for sid in class_student_ids:
            if sid not in seen:
                student_ids.append(sid)
                seen.add(sid)

    # 构建脱敏学生列表
    students_data: list[dict] = []
    for idx, sid in enumerate(sorted(student_ids), 1):
        code = f"学生-{idx:03d}"
        # 最新评价分数（不返回真实姓名）
        latest_score = db.scalar(
            select(EvaluationRecord.total_score)
            .where(
                EvaluationRecord.project_id == project_id,
                EvaluationRecord.student_id == sid,
                EvaluationRecord.total_score.is_not(None),
            )
            .order_by(EvaluationRecord.created_at.desc())
            .limit(1)
        )
        students_data.append(
            {
                "code": code,
                "real_name": None,  # 脱敏：不返回真实姓名
                "contact_hidden": True,
                "latest_score": latest_score,
            }
        )

    status_value = (
        project.status.value if hasattr(project.status, "value") else str(project.status)
    )
    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "status": status_value,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
        },
        "students": students_data,
        "anonymized": True,
        "note": "学生姓名已脱敏为编号；联系方式（手机/邮箱）已隐藏",
    }


def _ensure_closure_completeness(db: Session, project_id: str) -> None:
    """结项完整性检查：存在未发布反馈或未处理阻断问题时拒绝（409）。

    依据计划 Task 9 验收：存在未发布反馈或未处理阻断问题时给出明确提示。
    - 未发布反馈：EvaluationRecord.status 不在 [PUBLISHED, FINALIZED]。
    - 未处理阻断问题：QualityIssue.severity=BLOCKER 且 status=OPEN（关联项目 AI 任务）。
    """
    # 未发布评价
    unpublished_rows = list(
        db.scalars(
            select(EvaluationRecord.id).where(
                EvaluationRecord.project_id == project_id,
                ~EvaluationRecord.status.in_(
                    [EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED]
                ),
            )
        ).all()
    )
    if unpublished_rows:
        raise AppException(
            code=40903,
            message=(
                f"项目存在 {len(unpublished_rows)} 条未发布评价，无法结项；"
                f"请先发布或删除未发布反馈"
            ),
            status_code=409,
        )

    # 未处理阻断问题（关联项目的 AI 任务）
    open_blockers = list(
        db.scalars(
            select(QualityIssue.id)
            .join(AiJob, QualityIssue.job_id == AiJob.id)
            .where(
                AiJob.project_id == project_id,
                QualityIssue.severity == QualitySeverity.BLOCKER,
                QualityIssue.status == IssueStatus.OPEN,
            )
        ).all()
    )
    if open_blockers:
        raise AppException(
            code=40903,
            message=(
                f"项目存在 {len(open_blockers)} 条未处理阻断问题，无法结项；"
                f"请先处理或确认 wontfix"
            ),
            status_code=409,
        )


def get_project_subject_ids(db: Session, project_id: str) -> list[str]:
    return ProjectRepository(db).subject_ids(project_id)


def get_project_class_ids(db: Session, project_id: str) -> list[str]:
    return ProjectRepository(db).class_ids(project_id)


def list_project_students(db: Session, actor: User, project_id: str) -> list[dict]:
    """`GET /api/v1/projects/{project_id}/students` 服务实现（Task 1）。

    返回项目关联班级中启用学生，字段仅含 id/real_name/class_id/class_name。
    复用项目读权限策略：非项目教师、学生和跨校管理员返回 403。
    """
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_read(actor, project, repository.class_ids(project.id))
    rows = repository.list_active_students_in_project_classes(project.id)
    return [
        {
            "id": user.id,
            "real_name": user.display_name,
            "class_id": class_id,
            "class_name": class_name,
        }
        for user, class_id, class_name in rows
    ]


def is_student_assignable_to_project(db: Session, project_id: str, student_id: str) -> bool:
    """校验学生是否可分配到项目任务：属于项目关联班级且启用（Task 1）。"""
    repository = ProjectRepository(db)
    rows = repository.list_active_students_in_project_classes(project_id)
    return any(user.id == student_id for user, _cid, _cname in rows)


def _change_status(
    db: Session,
    actor: User,
    project_id: str,
    expected_status: ProjectStatus,
    target_status: ProjectStatus,
    action_name: str,
) -> Project:
    repository = ProjectRepository(db)
    project = _require_project(repository, project_id)
    ensure_can_manage(actor, project, repository.class_ids(project.id))
    ensure_not_archived(project)
    if project.status != expected_status:
        raise _illegal_transition(
            project.status,
            target_status,
            action_name,
            allowed_from=[expected_status],
        )
    project.status = target_status
    return _commit_and_refresh(db, project)


def _require_project(repository: ProjectRepository, project_id: str) -> Project:
    project = repository.get(project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def _illegal_transition(
    current_status: ProjectStatus,
    target_status: ProjectStatus,
    action_name: str,
    *,
    allowed_from: list[ProjectStatus],
    hint: str = "",
) -> AppException:
    """构造非法状态跃迁异常（统一 409）。

    响应包含当前状态、目标状态和允许操作，符合计划 4.3 要求。
    """
    current = current_status.value if hasattr(current_status, "value") else str(current_status)
    target = target_status.value if hasattr(target_status, "value") else str(target_status)
    allowed = ", ".join(s.value for s in allowed_from)
    message = f"项目状态不允许{action_name}，当前状态: {current}，目标状态: {target}，仅允许从 [{allowed}] 转入"
    if hint:
        message += f"；{hint}"
    return AppException(code=40901, message=message, status_code=409)


def _blocked_transition(blockers) -> AppException:
    """构造完整性阻断异常（409）。

    `blockers` 为 `validators.ValidationIssue` 列表；将其代码与说明
    拼接进 message，便于前端展示具体缺失项。
    """
    summary = "; ".join(f"{b.code}: {b.message}" for b in blockers)
    return AppException(
        code=40902,
        message=f"项目完整性检查未通过，不能激活: {summary}",
        status_code=409,
    )


def _commit_and_refresh(db: Session, project: Project) -> Project:
    _commit(db)
    db.refresh(project)
    return project


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
