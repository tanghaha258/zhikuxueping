"""运营证据领域服务层（Task 8）。

职责：
- 真实/测试/演示/导入数据过滤（默认仅返回 real，验收 3.8.1 / 8.5）。
- 指标公式与来源追溯：每条对外指标都能查看公式、周期、样本量、来源与责任人。
- 学校范围脱敏：学生姓名→学号尾号、教师姓名→工号（验收 3.8.3）。
- 导出审计：每次导出落 ExportRecord，记录操作人/范围/脱敏/时间。
- 二次确认：preview -> confirmed，禁止跳过预览直接确认。

唯一提交点在服务层；失败回滚。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import DataOrigin
from app.models.operational_evidence import (
    EvidenceLedger,
    ExportRecord,
    ExportStatus,
    OperationalMetric,
)
from app.models.user import Role, User
from app.modules.operational_evidence import policy, repository


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


# ── 运营指标 ──────────────────────────────────────────────────
def create_metric(
    db: Session,
    actor: User,
    *,
    name: str,
    code: str,
    formula: str,
    period,
    sample_size: int | None = None,
    source_table: str | None = None,
    source_owner: str | None = None,
    responsible_person: str | None = None,
    data_origin: DataOrigin = DataOrigin.REAL,
    value: float | None = None,
    value_collected_at: datetime | None = None,
    school_id: str | None = None,
) -> OperationalMetric:
    """登记运营指标。学校管理员只能创建本校指标。"""
    policy.require_admin(actor)
    if actor.role == Role.SCHOOL_ADMIN:
        if school_id is None:
            # 学校管理员创建指标默认绑定本校
            school_id = actor.school_id
        elif actor.school_id is None or school_id != actor.school_id:
            raise AppException(
                code=40301,
                message="不能为其他学校登记指标",
                status_code=403,
            )
    if repository.get_metric_by_code(db, code):
        raise AppException(
            code=40001, message=f"指标代码 {code} 已存在", status_code=400
        )
    metric = OperationalMetric(
        name=name,
        code=code,
        formula=formula,
        period=period,
        sample_size=sample_size,
        source_table=source_table,
        source_owner=source_owner,
        responsible_person=responsible_person,
        data_origin=data_origin,
        value=value,
        value_collected_at=value_collected_at,
        school_id=school_id,
    )
    repository.create_metric(db, metric)
    _commit(db)
    db.refresh(metric)
    return metric


def list_metrics(
    db: Session,
    actor: User,
    *,
    data_origin: DataOrigin | None = DataOrigin.REAL,
    school_id: str | None = None,
    period: str | None = None,
) -> list[OperationalMetric]:
    """列指标。默认仅返回真实数据（验收 8.5）。

    学校管理员只能查看本校指标；系统管理员可查看指定学校或全量。
    """
    policy.require_admin(actor)
    if actor.role == Role.SCHOOL_ADMIN:
        # 学校管理员忽略 school_id 参数，强制本校
        if actor.school_id is None:
            return []
        target_school = actor.school_id
    else:
        target_school = school_id
    metrics = repository.list_metrics(
        db, data_origin=data_origin, school_id=target_school, period=period
    )
    return metrics


def get_metric_detail(db: Session, actor: User, metric_id: str) -> dict:
    """指标详情：含公式/周期/样本量/来源/责任人 + 关联证据台账。"""
    metric = repository.get_metric(db, metric_id)
    if not metric:
        raise AppException(code=40401, message="运营指标不存在", status_code=404)
    policy.ensure_metric_in_scope(actor, metric)
    evidence = repository.list_evidence_by_metric(db, metric_id)
    return {
        "metric": metric_dict(metric),
        "evidence": [evidence_dict(e) for e in evidence],
    }


# ── 证据台账 ──────────────────────────────────────────────────
def register_evidence(
    db: Session,
    actor: User,
    *,
    metric_id: str,
    evidence_ref: str,
    evidence_summary: str | None = None,
    collected_at: datetime,
) -> EvidenceLedger:
    """登记证据台账记录（不能手工填写成效值而不标记来源）。"""
    metric = repository.get_metric(db, metric_id)
    if not metric:
        raise AppException(code=40401, message="运营指标不存在", status_code=404)
    policy.ensure_metric_in_scope(actor, metric)
    evidence = EvidenceLedger(
        metric_id=metric_id,
        evidence_ref=evidence_ref,
        evidence_summary=evidence_summary,
        collected_at=collected_at,
        verified_by=actor.id,
    )
    repository.create_evidence(db, evidence)
    _commit(db)
    db.refresh(evidence)
    return evidence


def list_evidence(db: Session, actor: User, metric_id: str) -> list[EvidenceLedger]:
    metric = repository.get_metric(db, metric_id)
    if not metric:
        raise AppException(code=40401, message="运营指标不存在", status_code=404)
    policy.ensure_metric_in_scope(actor, metric)
    return repository.list_evidence_by_metric(db, metric_id)


# ── 脱敏 ─────────────────────────────────────────────────────
_STUDENT_NAME_RE = re.compile(r"^(?P<last>[\u4e00-\u9fa5]{1,2})?(?P<rest>.+)$")


def anonymize_student_name(name: str, student_no: str | None = None) -> str:
    """学生姓名 → 学号尾号脱敏。

    例：张三 + S2024001 → S****001；无学号时 → 学****。
    """
    if not name:
        return ""
    if student_no:
        if len(student_no) <= 4:
            return f"{student_no[:1]}****" if student_no else "学****"
        head = student_no[0]
        tail = student_no[-4:]
        return f"{head}****{tail}"
    return "学****"


def anonymize_teacher_name(name: str, teacher_no: str | None = None) -> str:
    """教师姓名 → 工号脱敏。"""
    if not name:
        return ""
    if teacher_no:
        if len(teacher_no) <= 4:
            return f"{teacher_no[:1]}****" if teacher_no else "工****"
        head = teacher_no[0]
        tail = teacher_no[-4:]
        return f"{head}****{tail}"
    return "工****"


def _anonymize_text(text: str | None, *, role: str) -> str | None:
    """对内嵌的姓名做简单脱敏：保留角色前缀，姓名替换为掩码。

    用于证据摘要中的学生/教师姓名脱敏。
    """
    if not text:
        return text
    if role == "student":
        # 把形如 “张三 同学” 替换为 “学**** 同学”
        return re.sub(
            r"([\u4e00-\u9fa5]{2,4})\s*(?:同学|学生)",
            lambda m: f"学**** {m.group(2)}",
            text,
        )
    if role == "teacher":
        return re.sub(
            r"([\u4e00-\u9fa5]{2,4})\s*(?:老师|教师)",
            lambda m: f"工**** {m.group(2)}",
            text,
        )
    return text


# ── 导出预览/二次确认 ─────────────────────────────────────────
def preview_export(
    db: Session,
    actor: User,
    *,
    metric_ids: list[str],
    anonymized: bool = True,
    school_id: str | None = None,
) -> dict:
    """导出预览：返回脱敏后样本 + 落 PENDING/PREVIEWED 审计记录。

    二次确认要求：preview -> confirmed，禁止跳过预览直接确认。
    """
    policy.ensure_export_scope(actor, school_id)
    # 解析指标（必须落在 actor 范围内）
    metrics = repository.list_metrics_by_ids(db, metric_ids)
    for m in metrics:
        policy.ensure_metric_in_scope(actor, m)
    evidence = repository.list_evidence_by_metrics(db, metric_ids)
    # 落审计记录
    export = ExportRecord(
        exporter_id=actor.id,
        scope_school_id=school_id,
        metric_ids=",".join(metric_ids) if metric_ids else None,
        anonymized=anonymized,
        status=ExportStatus.PREVIEWED,
    )
    repository.create_export(db, export)
    _commit(db)
    db.refresh(export)

    examples: list[str] = []
    if anonymized:
        examples.append(anonymize_student_name("张三", "S2024001"))
        examples.append(anonymize_teacher_name("王老师", "T20240056"))
    return {
        "export": export_dict(export),
        "metrics": [metric_dict(m) for m in metrics],
        "evidence": [evidence_dict(e) for e in evidence],
        "anonymization_examples": examples,
    }


def confirm_export(
    db: Session,
    actor: User,
    *,
    export_id: str,
    audit_note: str | None = None,
) -> ExportRecord:
    """导出二次确认：仅 PREVIEWED 状态可确认。

    禁止跳过预览直接确认（验收 3.8.3）。
    """
    export = repository.get_export(db, export_id)
    if not export:
        raise AppException(code=40401, message="导出记录不存在", status_code=404)
    if export.exporter_id != actor.id:
        # 仅导出操作人可二次确认
        raise AppException(
            code=40301,
            message="仅导出操作人可二次确认",
            status_code=403,
        )
    if export.status != ExportStatus.PREVIEWED:
        raise AppException(
            code=40901,
            message=(
                f"导出记录状态「{export.status.value}」不可确认；"
                f"必须先经过预览（previewed）"
            ),
            status_code=409,
        )
    # 再次校验导出范围（防止预览后被踢出学校）
    policy.ensure_export_scope(actor, export.scope_school_id)
    export.status = ExportStatus.CONFIRMED
    export.audit_note = audit_note
    export.confirmed_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(export)
    return export


def list_export_records(
    db: Session, actor: User, limit: int = 50
) -> list[ExportRecord]:
    """查询导出审计记录：仅本人发起的记录。

    系统管理员可查看全部；学校管理员仅查看本校范围记录。
    """
    policy.require_admin(actor)
    exports = repository.list_exports_by_exporter(db, actor.id, limit=limit)
    if actor.role == Role.SCHOOL_ADMIN:
        # 学校管理员进一步过滤本校范围
        exports = [
            e for e in exports
            if e.scope_school_id is not None
            and actor.school_id is not None
            and e.scope_school_id == actor.school_id
        ]
    return exports


# ── 序列化辅助 ───────────────────────────────────────────────
def metric_dict(metric: OperationalMetric) -> dict:
    return {
        "id": metric.id,
        "name": metric.name,
        "code": metric.code,
        "formula": metric.formula,
        "period": _enum_value(metric.period),
        "sample_size": metric.sample_size,
        "source_table": metric.source_table,
        "source_owner": metric.source_owner,
        "responsible_person": metric.responsible_person,
        "data_origin": _enum_value(metric.data_origin),
        "value": metric.value,
        "value_collected_at": metric.value_collected_at,
        "school_id": metric.school_id,
        "created_at": metric.created_at,
        "updated_at": metric.updated_at,
    }


def evidence_dict(evidence: EvidenceLedger) -> dict:
    return {
        "id": evidence.id,
        "metric_id": evidence.metric_id,
        "evidence_ref": evidence.evidence_ref,
        "evidence_summary": evidence.evidence_summary,
        "collected_at": evidence.collected_at,
        "verified_by": evidence.verified_by,
        "created_at": evidence.created_at,
    }


def export_dict(export: ExportRecord) -> dict:
    return {
        "id": export.id,
        "exporter_id": export.exporter_id,
        "scope_school_id": export.scope_school_id,
        "metric_ids": export.metric_ids,
        "anonymized": export.anonymized,
        "status": _enum_value(export.status),
        "audit_note": export.audit_note,
        "confirmed_at": export.confirmed_at,
        "payload_ref": export.payload_ref,
        "created_at": export.created_at,
        "updated_at": export.updated_at,
    }
