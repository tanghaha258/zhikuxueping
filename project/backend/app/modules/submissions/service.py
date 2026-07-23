"""提交领域服务层（Task 6 扩展）。

职责：
- 基础 CRUD（保留原有 create/update/get/list 函数，向后兼容）。
- 订正状态机：draft -> submitted -> ai_reviewed -> teacher_reviewed
  -> returned -> resubmitted -> finalized；非法跃迁返回 409。
- 幂等提交键：同一 idempotency_key 重复提交返回已有版本，不生成重复记录。
- 二次评价入口：finalized 状态下学生可发起 reassess，教师可再次复核。
- 学生可见性聚合：项目空间、反馈视图、成长档案的数据装配。

唯一提交点在服务层；失败回滚。
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import (
    EvaluationStatus,
    ResourceTier,
    ReviewStatus,
    SubmissionReviewStatus,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectClass
from app.models.resource import Resource
from app.models.submission import Submission
from app.models.submission_revision import SubmissionRevision
from app.models.task import Task
from app.schemas.submission import SubmissionCreate, SubmissionUpdate


# ── 复核状态机（计划 4.3）────────────────────────────────────
_TRANSITIONS: dict[SubmissionReviewStatus, set[SubmissionReviewStatus]] = {
    SubmissionReviewStatus.DRAFT: {SubmissionReviewStatus.SUBMITTED},
    SubmissionReviewStatus.SUBMITTED: {
        SubmissionReviewStatus.AI_REVIEWED,
        SubmissionReviewStatus.TEACHER_REVIEWED,
        SubmissionReviewStatus.RETURNED,
    },
    SubmissionReviewStatus.AI_REVIEWED: {
        SubmissionReviewStatus.TEACHER_REVIEWED,
        SubmissionReviewStatus.RETURNED,
    },
    SubmissionReviewStatus.TEACHER_REVIEWED: {
        SubmissionReviewStatus.RETURNED,
        SubmissionReviewStatus.FINALIZED,
    },
    SubmissionReviewStatus.RETURNED: {SubmissionReviewStatus.RESUBMITTED},
    SubmissionReviewStatus.RESUBMITTED: {
        SubmissionReviewStatus.TEACHER_REVIEWED,
        SubmissionReviewStatus.RETURNED,
        SubmissionReviewStatus.FINALIZED,
    },
    SubmissionReviewStatus.FINALIZED: set(),  # 终态，二次评价走 reassess 流程
}


def _validate_transition(
    current: SubmissionReviewStatus, target: SubmissionReviewStatus
) -> None:
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise AppException(
            code=40901,
            message=(
                f"提交状态非法跃迁：当前「{current.value}」，"
                f"目标「{target.value}」，允许："
                f"{','.join(s.value for s in allowed) or '无（终态）'}"
            ),
            status_code=409,
        )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# 基础 CRUD（保留原有函数签名，向后兼容）
# ============================================================

def create_submission(db: Session, data: SubmissionCreate, student_id: str) -> Submission:
    statement = select(Submission).where(
        Submission.task_id == data.task_id,
        Submission.student_id == student_id,
    )
    existing = db.execute(statement).scalar_one_or_none()
    if existing:
        existing.content = data.content
        existing.file_urls = data.file_urls
        existing.submitted_at = datetime.now()
        existing.status = "submitted"
        existing.review_status = SubmissionReviewStatus.SUBMITTED
        db.commit()
        db.refresh(existing)
        return existing

    submission = Submission(
        task_id=data.task_id,
        student_id=student_id,
        content=data.content,
        file_urls=data.file_urls,
        submitted_at=datetime.now(),
        status="submitted",
        review_status=SubmissionReviewStatus.SUBMITTED,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def update_submission(
    db: Session,
    submission: Submission,
    data: SubmissionUpdate,
) -> Submission:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(submission, field, value)
    db.commit()
    db.refresh(submission)
    return submission


def get_submission(db: Session, submission_id: str) -> Submission | None:
    return db.get(Submission, submission_id)


def list_submissions_by_task(db: Session, task_id: str) -> list[Submission]:
    statement = (
        select(Submission)
        .where(Submission.task_id == task_id)
        .order_by(Submission.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def list_my_submissions(db: Session, student_id: str) -> list[Submission]:
    statement = (
        select(Submission)
        .where(Submission.student_id == student_id)
        .order_by(Submission.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_my_submission(
    db: Session,
    task_id: str,
    student_id: str,
) -> Submission | None:
    statement = select(Submission).where(
        Submission.task_id == task_id,
        Submission.student_id == student_id,
    )
    return db.execute(statement).scalar_one_or_none()


def bulk_import_submissions(db: Session, task_id: str, items: list) -> dict:
    task = db.get(Task, task_id)
    if not task:
        raise ValueError("task not found")

    created = []
    for item in items:
        submission = Submission(
            task_id=task_id,
            student_id=item.student_id,
            content=item.content or "",
            file_urls=[item.file_url],
            status="submitted",
        )
        db.add(submission)
        created.append(submission)
    db.commit()
    for submission in created:
        db.refresh(submission)
    return {"imported": len(created)}


# ============================================================
# 订正版本与状态机（Task 6 新增）
# ============================================================

def _next_attempt_number(db: Session, submission_id: str) -> int:
    stmt = select(SubmissionRevision.attempt_number).where(
        SubmissionRevision.submission_id == submission_id
    )
    current_max = max(
        (row[0] for row in db.execute(stmt).all()),
        default=0,
    )
    return current_max + 1


def _get_submission_or_404(db: Session, submission_id: str) -> Submission:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise AppException(code=40401, message="提交不存在", status_code=404)
    return submission


def save_draft(
    db: Session,
    task_id: str,
    student_id: str,
    content: str | None,
    file_urls: list[str] | None,
) -> Submission:
    """保存草稿：创建或更新 DRAFT 状态提交，不创建版本。"""
    submission = get_my_submission(db, task_id, student_id)
    if submission and submission.review_status != SubmissionReviewStatus.DRAFT:
        # 已提交的不能覆盖为草稿（除非退回后修改）
        if submission.review_status not in {
            SubmissionReviewStatus.RETURNED,
            SubmissionReviewStatus.DRAFT,
        }:
            raise AppException(
                code=40901,
                message=f"当前状态「{submission.review_status.value}」不允许保存草稿",
                status_code=409,
            )
    if submission is None:
        submission = Submission(
            task_id=task_id,
            student_id=student_id,
            content=content,
            file_urls=file_urls or [],
            status="draft",
            review_status=SubmissionReviewStatus.DRAFT,
        )
        db.add(submission)
    else:
        submission.content = content
        submission.file_urls = file_urls or []
        submission.status = "draft"
        submission.review_status = SubmissionReviewStatus.DRAFT
    _commit(db)
    db.refresh(submission)
    return submission


def submit_with_idempotency(
    db: Session,
    task_id: str,
    student_id: str,
    content: str | None,
    file_urls: list[str] | None,
    idempotency_key: str,
) -> tuple[Submission, SubmissionRevision, bool]:
    """幂等提交：同一 idempotency_key 不生成重复版本。

    返回 (submission, revision, created)：
    - created=True 表示新提交，revision 为新建版本。
    - created=False 表示重复点击，revision 为已有版本，直接返回。
    """
    # 幂等检查：同 key 已存在则直接返回
    if idempotency_key:
        existing = db.execute(
            select(SubmissionRevision).where(
                SubmissionRevision.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing:
            submission = db.get(Submission, existing.submission_id)
            if submission and submission.student_id == student_id:
                return submission, existing, False

    submission = get_my_submission(db, task_id, student_id)

    if submission is None:
        # 首次提交：创建提交线程
        submission = Submission(
            task_id=task_id,
            student_id=student_id,
            content=content,
            file_urls=file_urls or [],
            status="submitted",
            review_status=SubmissionReviewStatus.SUBMITTED,
            submitted_at=_now(),
        )
        db.add(submission)
        db.flush()
    else:
        # 状态机校验：DRAFT/RETURNED 可提交，其他状态需校验跃迁
        if submission.review_status == SubmissionReviewStatus.RETURNED:
            _validate_transition(submission.review_status, SubmissionReviewStatus.RESUBMITTED)
            submission.review_status = SubmissionReviewStatus.RESUBMITTED
        elif submission.review_status == SubmissionReviewStatus.DRAFT:
            _validate_transition(submission.review_status, SubmissionReviewStatus.SUBMITTED)
            submission.review_status = SubmissionReviewStatus.SUBMITTED
        else:
            raise AppException(
                code=40901,
                message=f"当前状态「{submission.review_status.value}」不允许提交",
                status_code=409,
            )
        submission.content = content
        submission.file_urls = file_urls or []
        submission.status = "submitted"
        submission.submitted_at = _now()

    # 创建版本
    attempt = _next_attempt_number(db, submission.id)
    revision = SubmissionRevision(
        submission_id=submission.id,
        attempt_number=attempt,
        content=content,
        file_urls=file_urls or [],
        idempotency_key=idempotency_key,
        review_status=submission.review_status,
        submitted_at=_now(),
    )
    db.add(revision)
    _commit(db)
    db.refresh(submission)
    db.refresh(revision)
    return submission, revision, True


def transition_submission(
    db: Session,
    submission_id: str,
    target: SubmissionReviewStatus,
    *,
    teacher_comment: str | None = None,
    teacher_private_note: str | None = None,
) -> Submission:
    """教师驱动的状态机迁移：退回 / 最终确认。"""
    submission = _get_submission_or_404(db, submission_id)
    _validate_transition(submission.review_status, target)

    submission.review_status = target
    # 镜像到旧 status 字段以兼容旧接口
    submission.status = target.value
    if target == SubmissionReviewStatus.RETURNED:
        submission.status = "returned"
    elif target == SubmissionReviewStatus.FINALIZED:
        submission.status = "finalized"

    # 更新最新版本的教师反馈
    latest = _latest_revision(db, submission_id)
    if latest:
        latest.review_status = target
        latest.reviewed_at = _now()
        if teacher_comment is not None:
            latest.teacher_comment = teacher_comment
        if teacher_private_note is not None:
            latest.teacher_private_note = teacher_private_note
    if teacher_comment is not None:
        submission.comment = teacher_comment
    _commit(db)
    db.refresh(submission)
    return submission


def return_submission(
    db: Session,
    submission_id: str,
    teacher_comment: str | None = None,
    teacher_private_note: str | None = None,
) -> Submission:
    """教师退回提交，学生可再次提交。"""
    return transition_submission(
        db,
        submission_id,
        SubmissionReviewStatus.RETURNED,
        teacher_comment=teacher_comment,
        teacher_private_note=teacher_private_note,
    )


def finalize_submission(
    db: Session,
    submission_id: str,
    teacher_comment: str | None = None,
) -> Submission:
    """教师最终确认提交，进入终态。"""
    return transition_submission(
        db,
        submission_id,
        SubmissionReviewStatus.FINALIZED,
        teacher_comment=teacher_comment,
    )


def request_reassessment(
    db: Session,
    submission_id: str,
    student_id: str,
    reason: str,
) -> Submission:
    """学生发起二次评价请求（finalized -> reassess 流程）。

    finalized 是状态机终态，二次评价通过创建新版本 + 标记 reassess_reason 实现，
    不破坏状态机不可逆性。新版本 review_status=RESUBMITTED，等待教师再次复核。
    """
    submission = _get_submission_or_404(db, submission_id)
    if submission.student_id != student_id:
        raise AppException(code=40301, message="只能对自己的提交发起二次评价", status_code=403)
    if submission.review_status != SubmissionReviewStatus.FINALIZED:
        raise AppException(
            code=40901,
            message=f"当前状态「{submission.review_status.value}」不允许发起二次评价",
            status_code=409,
        )
    if not reason or not reason.strip():
        raise AppException(code=40001, message="二次评价理由不能为空", status_code=400)

    # 二次评价：从 finalized 重新进入 RESUBMITTED
    submission.review_status = SubmissionReviewStatus.RESUBMITTED
    submission.status = "resubmitted"
    attempt = _next_attempt_number(db, submission.id)
    revision = SubmissionRevision(
        submission_id=submission.id,
        attempt_number=attempt,
        content=submission.content,
        file_urls=submission.file_urls or [],
        review_status=SubmissionReviewStatus.RESUBMITTED,
        reassess_reason=reason.strip(),
        submitted_at=_now(),
    )
    db.add(revision)
    _commit(db)
    db.refresh(submission)
    return submission


def _latest_revision(db: Session, submission_id: str) -> SubmissionRevision | None:
    stmt = (
        select(SubmissionRevision)
        .where(SubmissionRevision.submission_id == submission_id)
        .order_by(SubmissionRevision.attempt_number.desc())
    )
    return db.execute(stmt).scalars().first()


def list_revisions(db: Session, submission_id: str) -> list[SubmissionRevision]:
    stmt = (
        select(SubmissionRevision)
        .where(SubmissionRevision.submission_id == submission_id)
        .order_by(SubmissionRevision.attempt_number.asc())
    )
    return list(db.execute(stmt).scalars().all())


# ============================================================
# 学生可见性聚合（Task 6 新增）
# ============================================================

def get_student_project_view(
    db: Session,
    project_id: str,
    student_class_id: str | None,
) -> dict[str, Any]:
    """学生视角项目空间：只读设计 + 被授权的三级资源。

    资源授权规则（计划 3.5.2/3.7.2）：
    - foundation：所有学生可见。
    - enhancement：默认可见。
    - extension：默认可见但不展示负面分层名称（前端友好展示）。
    - review_status != PUBLISHED 的资源不向学生展示。
    """
    project = db.get(Project, project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)

    # 学生只能访问自己班级被分配的项目
    if student_class_id:
        assigned = db.execute(
            select(ProjectClass).where(
                ProjectClass.project_id == project_id,
                ProjectClass.class_id == student_class_id,
            )
        ).scalar_one_or_none()
        if not assigned:
            raise AppException(
                code=40301, message="无权访问该项目", status_code=403
            )

    # 只读设计：真实问题
    from app.models.project_design import ProjectProblem

    problem = db.execute(
        select(ProjectProblem).where(
            ProjectProblem.project_id == project_id,
            ProjectProblem.is_current.is_(True),
        )
    ).scalars().first()

    # 任务列表（仅 published 及以后状态）
    tasks = list(
        db.execute(
            select(Task).where(Task.project_id == project_id)
        ).scalars().all()
    )
    visible_tasks = [
        t for t in tasks
        if t.publish_status.value not in ("draft", "scheduled")
    ]

    # 资源：仅 PUBLISHED，按 tier 分组
    resources = list(
        db.execute(
            select(Resource).where(Resource.project_id == project_id)
        ).scalars().all()
    )
    tiered_resources = _filter_published_resources(resources)

    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "status": project.status.value if hasattr(project.status, "value") else str(project.status),
        },
        "problem": _problem_dict(problem),
        "tasks": [_task_summary(t) for t in visible_tasks],
        "resources": tiered_resources,
    }


def _filter_published_resources(resources: list[Resource]) -> dict[str, list[dict]]:
    """按层级分组已发布资源，不展示负面分层名称。"""
    tier_labels = {
        ResourceTier.FOUNDATION: "基础资源",
        ResourceTier.ENHANCEMENT: "进阶资源",
        ResourceTier.EXTENSION: "拓展资源",
    }
    grouped: dict[str, list[dict]] = {"foundation": [], "enhancement": [], "extension": []}
    for r in resources:
        if r.review_status != ReviewStatus.PUBLISHED:
            continue
        tier = r.tier
        if tier is None:
            continue
        tier_key = tier.value if hasattr(tier, "value") else str(tier)
        if tier_key not in grouped:
            continue
        grouped[tier_key].append({
            "id": r.id,
            "title": r.title,
            "res_type": r.res_type,
            "url": r.url,
            "tier": tier_key,
            "tier_label": tier_labels.get(tier, tier_key),
            "stage": r.stage.value if r.stage and hasattr(r.stage, "value") else None,
            "usage_tip": r.usage_tip,
        })
    return grouped


def _problem_dict(problem) -> dict | None:
    if not problem:
        return None
    return {
        "context": problem.context,
        "object": problem.object,
        "audience": problem.audience,
        "constraints": problem.constraints,
        "deliverable": problem.deliverable,
        "usage": problem.usage,
    }


def _task_summary(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "stage": task.stage.value if task.stage and hasattr(task.stage, "value") else None,
        "tier": task.tier.value if task.tier and hasattr(task.tier, "value") else None,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "max_score": task.max_score,
        "submission_type": task.submission_type.value if task.submission_type and hasattr(task.submission_type, "value") else None,
        "max_attempts": task.max_attempts,
    }


def get_student_feedback(db: Session, submission_id: str) -> dict[str, Any]:
    """学生视角反馈视图：仅展示已发布评价 + 订正入口 + 版本记录。

    隐藏：
    - 教师私有备注（teacher_private_note）。
    - 未发布（status != PUBLISHED/FINALIZED）的评价记录。
    - 其他学生的提交。
    """
    submission = _get_submission_or_404(db, submission_id)
    revisions = list_revisions(db, submission_id)

    # 已发布的评价记录（仅 published/finalized）
    records = list(
        db.execute(
            select(EvaluationRecord).where(
                EvaluationRecord.student_id == submission.student_id,
                EvaluationRecord.task_id == submission.task_id,
            )
        ).scalars().all()
    )
    visible_records = [
        r for r in records
        if r.status in {EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED}
    ]

    return {
        "submission": {
            "id": submission.id,
            "task_id": submission.task_id,
            "review_status": submission.review_status.value,
            "content": submission.content,
            "file_urls": submission.file_urls,
            "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        },
        "revisions": [_revision_student_dict(r) for r in revisions],
        "evaluations": [_evaluation_student_dict(r) for r in visible_records],
        "can_resubmit": submission.review_status == SubmissionReviewStatus.RETURNED,
        "can_request_reassess": submission.review_status == SubmissionReviewStatus.FINALIZED,
    }


def _revision_student_dict(revision: SubmissionRevision) -> dict:
    """学生可见的版本信息：隐藏教师私有备注。"""
    return {
        "id": revision.id,
        "attempt_number": revision.attempt_number,
        "content": revision.content,
        "file_urls": revision.file_urls,
        "review_status": revision.review_status.value,
        "teacher_comment": revision.teacher_comment,
        # teacher_private_note 不返回给学生
        "reassess_reason": revision.reassess_reason,
        "submitted_at": revision.submitted_at.isoformat() if revision.submitted_at else None,
        "reviewed_at": revision.reviewed_at.isoformat() if revision.reviewed_at else None,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


def _evaluation_student_dict(record: EvaluationRecord) -> dict:
    """学生可见的评价记录：仅展示已发布字段。"""
    return {
        "id": record.id,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "source": record.source.value if hasattr(record.source, "value") else str(record.source),
        "total_score": record.total_score,
        "comment": record.comment,
        "published_at": record.published_at.isoformat() if record.published_at else None,
        "confirmed_by": record.confirmed_by,
    }


def get_growth_portfolio(db: Session, student_id: str) -> dict[str, Any]:
    """成长档案：目标达成、证据、改进轨迹。

    不显示公开横向排名；缺失周期显示未采集，不补零。
    """
    submissions = list_my_submissions(db, student_id)

    # 按提交线程聚合订正轨迹
    trajectories: list[dict] = []
    for sub in submissions:
        revisions = list_revisions(db, sub.id)
        if not revisions:
            continue
        task = db.get(Task, sub.task_id)
        trajectories.append({
            "task_id": sub.task_id,
            "task_title": task.title if task else None,
            "submission_id": sub.id,
            "review_status": sub.review_status.value,
            "attempt_count": len(revisions),
            "first_submitted_at": revisions[0].submitted_at.isoformat() if revisions[0].submitted_at else None,
            "latest_submitted_at": revisions[-1].submitted_at.isoformat() if revisions[-1].submitted_at else None,
            "has_reassessment": any(r.reassess_reason for r in revisions),
        })

    # 已发布评价记录
    records = list(
        db.execute(
            select(EvaluationRecord).where(
                EvaluationRecord.student_id == student_id,
                EvaluationRecord.status.in_([
                    EvaluationStatus.PUBLISHED,
                    EvaluationStatus.FINALIZED,
                ]),
            )
        ).scalars().all()
    )
    evidence_summary = {
        "total_evaluations": len(records),
        "average_score": (
            sum(r.total_score for r in records if r.total_score is not None)
            / max(1, len([r for r in records if r.total_score is not None]))
        ) if any(r.total_score is not None for r in records) else None,
        "by_source": _group_by_source(records),
    }

    return {
        "trajectories": trajectories,
        "evidence_summary": evidence_summary,
        "note": "缺失周期显示未采集，不补零；不提供公开横向排名。",
    }


def _group_by_source(records: list[EvaluationRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in records:
        key = r.source.value if hasattr(r.source, "value") else str(r.source)
        counts[key] = counts.get(key, 0) + 1
    return counts


# ============================================================
# 序列化辅助（供路由层使用）
# ============================================================

def revision_dict(revision: SubmissionRevision) -> dict:
    """完整版本字典（教师视角，含私有备注）。"""
    return {
        "id": revision.id,
        "submission_id": revision.submission_id,
        "attempt_number": revision.attempt_number,
        "content": revision.content,
        "file_urls": revision.file_urls,
        "idempotency_key": revision.idempotency_key,
        "review_status": revision.review_status.value,
        "teacher_comment": revision.teacher_comment,
        "teacher_private_note": revision.teacher_private_note,
        "reassess_reason": revision.reassess_reason,
        "submitted_at": revision.submitted_at.isoformat() if revision.submitted_at else None,
        "reviewed_at": revision.reviewed_at.isoformat() if revision.reviewed_at else None,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }
