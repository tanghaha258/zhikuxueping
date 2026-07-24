"""管理后台驾驶舱（Task 8 接入运营证据）。

阶段验收：任何对外指标都能查看公式、周期、样本量、数据来源和责任人，
且默认不含非真实数据（验收 3.8.1 / 8.5）。

设计要点：
- 教师/学生/项目统计仅计入 data_origin=real 的记录；测试/演示/导入数据不污染指标。
- 引入运营指标计数与样本，便于前端 ECharts 展示真实接口而非 CSS 占位。
- 学校管理员只能查看本校；系统管理员可查看全量。
"""
from datetime import datetime, timedelta, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.deps import require_roles
from app.core.response import success_response
from app.db.session import get_db
from app.models.enums import (
    DataOrigin,
    EvaluationStatus,
    SubmissionReviewStatus,
    TaskPublishStatus,
)
from app.models.user import Role, User
from app.models.project import Project, ProjectStatus
from app.models.project_stage import ProjectStageProgress
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation_plan import EvaluationRecord
from app.models.ai_job import AiJob, AiJobStatus
from app.models.audit_log import AuditLog
from app.models.operational_evidence import OperationalMetric
from app.schemas.project_workspace import PHASE_ORDER

router = APIRouter(prefix="/dashboard", tags=["管理后台"])


def _school_filter(actor: User, column):
    """学校管理员强制过滤本校；系统管理员不过滤。"""
    if actor.role == Role.SCHOOL_ADMIN:
        if actor.school_id is None:
            # 无学校绑定的学校管理员只能看到空集，避免越权
            return column == "__NO_SCHOOL__"
        return column == actor.school_id
    return None  # 不加过滤


@router.get("/stats", summary="管理后台统计（默认仅真实数据）")
def admin_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    now_naive = datetime.utcnow()
    week_ago = now_naive - timedelta(days=7)
    today = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── 用户与项目统计：过滤 data_origin=real（验收 8.5）────────
    teacher_stmt = select(func.count()).select_from(User).where(User.role == "teacher")
    student_stmt = select(func.count()).select_from(User).where(User.role == "student")
    # Project 增加 school_id 过滤（学校管理员只看本校）
    school_clause = _school_filter(current_user, Project.school_id)
    project_stmt = select(func.count()).select_from(Project).where(
        # 默认仅真实数据；历史项目 data_origin 为 NULL，作为兼容保留
        (Project.data_origin == DataOrigin.REAL) | (Project.data_origin.is_(None))
    )
    if school_clause is not None:
        project_stmt = project_stmt.where(school_clause)
    teacher_count = db.execute(teacher_stmt).scalar() or 0
    student_count = db.execute(student_stmt).scalar() or 0
    project_count = db.execute(project_stmt).scalar() or 0

    # ── 周活与日活（审计日志不区分 data_origin，直接统计）────────
    weekly_active = db.execute(
        select(func.count(func.distinct(AuditLog.user_id)))
        .where(AuditLog.created_at >= week_ago)
    ).scalar() or 0

    daily_stats = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_end = day + timedelta(days=1)
        active = db.execute(
            select(func.count(func.distinct(AuditLog.user_id)))
            .where(AuditLog.created_at >= day)
            .where(AuditLog.created_at < day_end)
        ).scalar() or 0
        new_tasks_stmt = (
            select(func.count())
            .select_from(Task)
            .where(Task.created_at >= day)
            .where(Task.created_at < day_end)
        )
        new_tasks = db.execute(new_tasks_stmt).scalar() or 0
        daily_stats.append({
            "date": day.strftime("%Y-%m-%d"),
            "active_users": active,
            "new_tasks": new_tasks,
        })

    logs = db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    ).scalars().all()

    recent_activities = []
    for log in logs:
        ts = log.created_at
        if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        time_diff = now_naive - ts
        if time_diff.total_seconds() < 60:
            time_str = "刚刚"
        elif time_diff.total_seconds() < 3600:
            time_str = f"{int(time_diff.total_seconds() // 60)} 分钟前"
        elif time_diff.total_seconds() < 86400:
            time_str = f"{int(time_diff.total_seconds() // 3600)} 小时前"
        else:
            days = int(time_diff.total_seconds() // 86400)
            time_str = f"{days} 天前" if days <= 7 else log.created_at.strftime("%m-%d")
        recent_activities.append({
            "user": log.username or "系统",
            "action": log.action + (f"「{log.detail}」" if log.detail else ""),
            "time": time_str,
        })

    # ── 运营指标概览（默认仅真实数据，验收 3.8.1）──────────────
    metric_stmt = select(OperationalMetric).where(
        OperationalMetric.data_origin == DataOrigin.REAL
    )
    school_metric_clause = _school_filter(current_user, OperationalMetric.school_id)
    if school_metric_clause is not None:
        # 学校管理员只看本校指标；NULL 跨校指标对学校管理员不可见
        metric_stmt = metric_stmt.where(OperationalMetric.school_id == school_metric_clause)
    metrics = list(db.execute(metric_stmt).scalars().all())
    metric_overview = [
        {
            "id": m.id,
            "name": m.name,
            "code": m.code,
            "formula": m.formula,
            "period": m.period.value if m.period else None,
            "sample_size": m.sample_size,
            "source_table": m.source_table,
            "source_owner": m.source_owner,
            "responsible_person": m.responsible_person,
            "value": m.value,
            "value_collected_at": m.value_collected_at,
        }
        for m in metrics
    ]

    return success_response(data={
        "teacher_count": teacher_count,
        "student_count": student_count,
        "project_count": project_count,
        "weekly_active_users": weekly_active,
        "daily_stats": daily_stats,
        "recent_activities": recent_activities,
        # 阶段验收：对外指标展示公式/周期/样本量/来源/责任人
        "metric_overview": metric_overview,
        "metric_count": len(metric_overview),
        # 数据口径标识：默认仅真实数据
        "data_origin_filter": "real",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


@router.get("/operational-metrics/summary", summary="运营指标汇总（默认仅真实数据）")
def operational_metrics_summary(
    data_origin: DataOrigin = Query(
        DataOrigin.REAL, description="数据来源过滤；默认仅 real"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    """运营指标汇总端点：用于管理员驾驶舱 ECharts 展示真实接口数据。

    默认 data_origin=real；学校管理员只能查看本校；系统管理员可指定其他来源。
    """
    stmt = select(OperationalMetric)
    if data_origin == DataOrigin.REAL:
        # 兼容历史 NULL 数据，仅在 real 过滤下叠加
        stmt = stmt.where(
            (OperationalMetric.data_origin == DataOrigin.REAL)
            | (OperationalMetric.data_origin.is_(None))
        )
    else:
        stmt = stmt.where(OperationalMetric.data_origin == data_origin)
    school_clause = _school_filter(current_user, OperationalMetric.school_id)
    if school_clause is not None:
        stmt = stmt.where(OperationalMetric.school_id == school_clause)
    metrics = list(db.execute(stmt).scalars().all())
    return success_response(
        {
            "items": [
                {
                    "id": m.id,
                    "name": m.name,
                    "code": m.code,
                    "formula": m.formula,
                    "period": m.period.value if m.period else None,
                    "sample_size": m.sample_size,
                    "source_table": m.source_table,
                    "source_owner": m.source_owner,
                    "responsible_person": m.responsible_person,
                    "data_origin": m.data_origin.value if m.data_origin else None,
                    "value": m.value,
                    "value_collected_at": m.value_collected_at,
                    "school_id": m.school_id,
                }
                for m in metrics
            ],
            "total": len(metrics),
            "data_origin_filter": data_origin.value,
        }
    )


# ============================================================
# 教师工作台（Task 5）
# ============================================================
# 工作台只返回当前教师可管理范围内的真实待办与活跃项目：
# - teacher：仅自己创建的项目
# - school_admin：仅本校教师项目；无 school_id 视为空集，避免越权
# 不引入静态待办、模拟事实或跨教师/跨校数据；每个待办带 route，
# 点击直接进入所属项目和阶段。
_PHASE_LABELS = {
    "diagnosis": "学情诊断",
    "design": "跨学科设计",
    "preparation": "备课与准备",
    "implementation": "学习实施",
    "evaluation": "多元评价",
    "improvement": "改进循环",
    "closure": "结项归档",
}

_PUBLISHED_EVAL_STATES = (EvaluationStatus.PUBLISHED, EvaluationStatus.FINALIZED)
_REVIEW_PENDING_STATES = (SubmissionReviewStatus.SUBMITTED, SubmissionReviewStatus.AI_REVIEWED)
_DEADLINE_HORIZON_DAYS = 7
_PHASE_ROUTE_SUFFIX = {
    "diagnosis": "diagnosis",
    "design": "design",
    "preparation": "preparation",
    "implementation": "tasks",
    "evaluation": "evaluation",
    "improvement": "insights",
    "closure": "closure",
}


def _project_route(project_id: str, phase: Optional[str] = None) -> str:
    """生成项目工作区路由；phase 指定时指向阶段子页。"""
    if phase is None:
        return f"/teacher/projects/{project_id}/overview"
    suffix = _PHASE_ROUTE_SUFFIX.get(phase, phase)
    return f"/teacher/projects/{project_id}/{suffix}"


def _scoped_project_ids(db: Session, actor: User) -> list[str]:
    """返回当前教师可管理范围的项目 ID 列表。

    teacher 仅看自己创建的项目；school_admin 仅看本校项目（无 school_id 为空集）。
    """
    if actor.role == Role.TEACHER:
        stmt = select(Project.id).where(Project.creator_id == actor.id)
    elif actor.role == Role.SCHOOL_ADMIN:
        if not actor.school_id:
            return []
        stmt = select(Project.id).where(Project.school_id == actor.school_id)
    else:
        return []
    return [row[0] for row in db.execute(stmt).all()]


def _project_titles(db: Session, project_ids: list[str]) -> dict[str, str]:
    if not project_ids:
        return {}
    rows = db.execute(
        select(Project.id, Project.title).where(Project.id.in_(project_ids))
    ).all()
    return {pid: title for pid, title in rows}


def _active_projects(db: Session, project_ids: list[str]) -> list[dict]:
    """活跃项目：带当前阶段与完成度，route 指向项目总览。"""
    if not project_ids:
        return []
    projects = list(
        db.scalars(
            select(Project).where(
                Project.id.in_(project_ids),
                Project.status == ProjectStatus.ACTIVE,
            )
        ).all()
    )
    if not projects:
        return []
    # 批量查阶段进度
    stage_rows = db.execute(
        select(
            ProjectStageProgress.project_id,
            ProjectStageProgress.phase,
            ProjectStageProgress.status,
        ).where(ProjectStageProgress.project_id.in_([p.id for p in projects]))
    ).all()
    stages_by_project: dict[str, dict[str, str]] = {}
    for pid, phase, status in stage_rows:
        stages_by_project.setdefault(pid, {})[phase] = status

    result = []
    for p in projects:
        stages = stages_by_project.get(p.id, {})
        current_phase = next(
            (ph for ph in PHASE_ORDER if stages.get(ph) != "completed"),
            None,
        )
        completed = sum(1 for ph in PHASE_ORDER if stages.get(ph) == "completed")
        completion = round(completed / len(PHASE_ORDER), 2) if PHASE_ORDER else 0.0
        result.append(
            {
                "id": p.id,
                "title": p.title,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
                "current_phase": current_phase,
                "current_phase_label": _PHASE_LABELS.get(current_phase) if current_phase else None,
                "completion": completion,
                "route": _project_route(p.id),
            }
        )
    return result


def _tasks_to_publish(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """草稿任务待发布。"""
    if not project_ids:
        return []
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.project_id.in_(project_ids),
                Task.publish_status == TaskPublishStatus.DRAFT,
            ).order_by(Task.created_at.desc())
        ).all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "project_id": t.project_id,
            "project_title": titles.get(t.project_id, ""),
            "publish_status": t.publish_status.value if hasattr(t.publish_status, "value") else str(t.publish_status),
            "route": _project_route(t.project_id, "implementation"),
        }
        for t in tasks
    ]


def _submissions_to_review(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """已提交待复核（submitted / ai_reviewed）。"""
    if not project_ids:
        return []
    rows = db.execute(
        select(Submission, Task)
        .join(Task, Submission.task_id == Task.id)
        .where(
            Task.project_id.in_(project_ids),
            Submission.review_status.in_(_REVIEW_PENDING_STATES),
        )
        .order_by(Submission.submitted_at.desc())
    ).all()
    return [
        {
            "id": sub.id,
            "task_id": task.id,
            "task_title": task.title,
            "project_id": task.project_id,
            "project_title": titles.get(task.project_id, ""),
            "student_id": sub.student_id,
            "review_status": sub.review_status.value if hasattr(sub.review_status, "value") else str(sub.review_status),
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "route": _project_route(task.project_id, "evaluation"),
        }
        for sub, task in rows
    ]


def _feedback_to_publish(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """已确认未发布评价待发布。"""
    if not project_ids:
        return []
    records = list(
        db.scalars(
            select(EvaluationRecord).where(
                EvaluationRecord.project_id.in_(project_ids),
                EvaluationRecord.status.not_in(_PUBLISHED_EVAL_STATES),
                EvaluationRecord.confirmed_at.is_not(None),
            ).order_by(EvaluationRecord.confirmed_at.desc())
        ).all()
    )
    return [
        {
            "id": r.id,
            "project_id": r.project_id,
            "project_title": titles.get(r.project_id, ""),
            "student_id": r.student_id,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "confirmed_at": r.confirmed_at.isoformat() if r.confirmed_at else None,
            "route": _project_route(r.project_id, "evaluation"),
        }
        for r in records
    ]


def _ai_to_review(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """AI 已成功但未审核的任务。"""
    if not project_ids:
        return []
    jobs = list(
        db.scalars(
            select(AiJob).where(
                AiJob.project_id.in_(project_ids),
                AiJob.status == AiJobStatus.SUCCEEDED,
                AiJob.reviewed_by.is_(None),
            ).order_by(AiJob.created_at.desc())
        ).all()
    )
    return [
        {
            "id": j.id,
            "project_id": j.project_id,
            "project_title": titles.get(j.project_id, "") if j.project_id else "",
            "scene": j.scene.value if hasattr(j.scene, "value") else str(j.scene),
            "status": j.status.value if hasattr(j.status, "value") else str(j.status),
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "route": _project_route(j.project_id, "evaluation") if j.project_id else None,
        }
        for j in jobs
    ]


def _deadlines(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """未来 7 天内截止的已发布任务。"""
    if not project_ids:
        return []
    # SQLite 不保留时区信息，读出的 deadline 为 naive datetime；
    # 统一使用 naive UTC 与数据库一致，避免 offset-aware/naive 相减报错。
    now = datetime.utcnow()
    horizon = now + timedelta(days=_DEADLINE_HORIZON_DAYS)
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.project_id.in_(project_ids),
                Task.publish_status == TaskPublishStatus.PUBLISHED,
                Task.deadline.is_not(None),
                Task.deadline >= now,
                Task.deadline <= horizon,
            ).order_by(Task.deadline.asc())
        ).all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "project_id": t.project_id,
            "project_title": titles.get(t.project_id, ""),
            "deadline": t.deadline.isoformat() if t.deadline else None,
            "days_left": (t.deadline - now).days if t.deadline else None,
            "route": _project_route(t.project_id, "implementation"),
        }
        for t in tasks
    ]


def _learning_alerts(db: Session, project_ids: list[str], titles: dict[str, str]) -> list[dict]:
    """已发布任务无任何提交 → 学习预警。

    基于真实提交数据：任务已发布但 submissions 表无对应记录。
    """
    if not project_ids:
        return []
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.project_id.in_(project_ids),
                Task.publish_status == TaskPublishStatus.PUBLISHED,
            )
        ).all()
    )
    if not tasks:
        return []
    task_ids = [t.id for t in tasks]
    # 有提交的 task_id 集合
    submitted_task_ids = {
        row[0]
        for row in db.execute(
            select(Submission.task_id).where(Submission.task_id.in_(task_ids))
        ).all()
    }
    alerts = []
    for t in tasks:
        if t.id in submitted_task_ids:
            continue
        alerts.append(
            {
                "id": t.id,
                "type": "no_submission",
                "task_id": t.id,
                "task_title": t.title,
                "project_id": t.project_id,
                "project_title": titles.get(t.project_id, ""),
                "message": f"任务「{t.title}」已发布但尚无学生提交",
                "route": _project_route(t.project_id, "evidence"),
            }
        )
    return alerts


@router.get("/teacher-workbench", summary="教师工作台数据")
def teacher_workbench(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    """返回教师可管理范围内的真实待办与活跃项目。

    所有条目均来自当前教师可管理范围（teacher=自己创建的项目；
    school_admin=本校项目；无 school_id 的 school_admin 为空集）。
    不引入静态待办、模拟事实或跨教师/跨校数据；每个待办带 route，
    点击直接进入所属项目和阶段。
    """
    project_ids = _scoped_project_ids(db, current_user)
    titles = _project_titles(db, project_ids)
    return success_response(
        data={
            "active_projects": _active_projects(db, project_ids),
            "tasks_to_publish": _tasks_to_publish(db, project_ids, titles),
            "submissions_to_review": _submissions_to_review(db, project_ids, titles),
            "feedback_to_publish": _feedback_to_publish(db, project_ids, titles),
            "ai_to_review": _ai_to_review(db, project_ids, titles),
            "deadlines": _deadlines(db, project_ids, titles),
            "learning_alerts": _learning_alerts(db, project_ids, titles),
        }
    )
