"""运营证据领域权限策略（Task 8）。

权限规则：
- 系统管理员（admin）：可访问所有指标、跨校汇总与跨校导出。
- 学校管理员（school_admin）：仅可访问本校指标与证据；导出范围不可越校。
- 教师/学生：无权访问运营证据（驾驶舱仅管理员可见，验收 3.8.1）。
- 脱敏默认开启；跨校导出仅系统管理员可执行。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.operational_evidence import OperationalMetric
from app.models.user import Role, User


def require_admin(actor: User) -> None:
    """运营证据操作仅限管理员（admin / school_admin）。"""
    if actor.role not in {Role.ADMIN, Role.SCHOOL_ADMIN}:
        raise AppException(
            code=40301,
            message="无权访问运营证据：仅管理员可操作",
            status_code=403,
        )


def ensure_can_access_school(actor: User, school_id: str | None) -> None:
    """校验访问学校范围。

    - 系统管理员：可访问任意学校，school_id 为 None 表示跨校汇总。
    - 学校管理员：仅可访问本校；school_id 为 None（跨校）拒绝。
    """
    require_admin(actor)
    if actor.role == Role.SCHOOL_ADMIN:
        if school_id is None:
            raise AppException(
                code=40301,
                message="学校管理员不能跨校访问运营证据",
                status_code=403,
            )
        if actor.school_id is None or school_id != actor.school_id:
            raise AppException(
                code=40301,
                message="不能访问其他学校的运营证据",
                status_code=403,
            )


def ensure_metric_in_scope(actor: User, metric: OperationalMetric) -> None:
    """指标必须落在 actor 可访问的学校范围内。"""
    require_admin(actor)
    if actor.role == Role.SCHOOL_ADMIN:
        # 学校管理员：指标必须属于本校（跨校汇总指标 school_id 为 None 也拒绝）
        if metric.school_id is None or actor.school_id is None or metric.school_id != actor.school_id:
            raise AppException(
                code=40301,
                message="指标超出本校范围，无权访问",
                status_code=403,
            )


def ensure_export_scope(actor: User, scope_school_id: str | None) -> None:
    """导出范围校验：学校管理员不能跨校导出。"""
    require_admin(actor)
    if actor.role == Role.SCHOOL_ADMIN:
        if scope_school_id is None:
            raise AppException(
                code=40301,
                message="学校管理员不能发起跨校导出",
                status_code=403,
            )
        if actor.school_id is None or scope_school_id != actor.school_id:
            raise AppException(
                code=40301,
                message="不能导出其他学校的运营证据",
                status_code=403,
            )


def filter_visible_metrics(
    db: Session,  # noqa: ARG001 — 保持与其他 policy 函数签名一致，便于扩展
    actor: User,
    metrics: list[OperationalMetric],
) -> list[OperationalMetric]:
    """按 actor 范围过滤可见指标。"""
    require_admin(actor)
    if actor.role == Role.ADMIN:
        return metrics
    # school_admin：仅返回本校指标
    if actor.school_id is None:
        return []
    return [m for m in metrics if m.school_id == actor.school_id]
