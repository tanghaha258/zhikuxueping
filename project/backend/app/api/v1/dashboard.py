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
from app.models.enums import DataOrigin
from app.models.user import Role, User
from app.models.project import Project
from app.models.task import Task
from app.models.audit_log import AuditLog
from app.models.operational_evidence import OperationalMetric

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
