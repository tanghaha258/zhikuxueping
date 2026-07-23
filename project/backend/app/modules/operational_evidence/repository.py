"""运营证据领域持久化操作。

函数式 repository，唯一提交点在服务层；本模块只负责查询与对象装配。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import DataOrigin
from app.models.operational_evidence import (
    EvidenceLedger,
    ExportRecord,
    OperationalMetric,
)


# ── OperationalMetric ────────────────────────────────────────
def create_metric(db: Session, metric: OperationalMetric) -> OperationalMetric:
    db.add(metric)
    db.flush()
    return metric


def get_metric(db: Session, metric_id: str) -> OperationalMetric | None:
    return db.get(OperationalMetric, metric_id)


def get_metric_by_code(db: Session, code: str) -> OperationalMetric | None:
    return db.execute(
        select(OperationalMetric).where(OperationalMetric.code == code)
    ).scalars().first()


def list_metrics(
    db: Session,
    *,
    data_origin: DataOrigin | None = DataOrigin.REAL,
    school_id: str | None = None,
    period: str | None = None,
    limit: int = 200,
) -> list[OperationalMetric]:
    """列指标。默认仅返回真实数据（验收 3.8.1 / 8.5）。"""
    stmt = select(OperationalMetric).order_by(OperationalMetric.created_at.desc())
    if data_origin is not None:
        stmt = stmt.where(OperationalMetric.data_origin == data_origin)
    if school_id is not None:
        stmt = stmt.where(OperationalMetric.school_id == school_id)
    if period is not None:
        stmt = stmt.where(OperationalMetric.period == period)
    stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_metrics(
    db: Session,
    *,
    data_origin: DataOrigin | None = DataOrigin.REAL,
    school_id: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(OperationalMetric)
    if data_origin is not None:
        stmt = stmt.where(OperationalMetric.data_origin == data_origin)
    if school_id is not None:
        stmt = stmt.where(OperationalMetric.school_id == school_id)
    return int(db.execute(stmt).scalar() or 0)


def list_metrics_by_ids(
    db: Session, metric_ids: list[str]
) -> list[OperationalMetric]:
    if not metric_ids:
        return []
    stmt = select(OperationalMetric).where(OperationalMetric.id.in_(metric_ids))
    return list(db.execute(stmt).scalars().all())


# ── EvidenceLedger ──────────────────────────────────────────
def create_evidence(db: Session, evidence: EvidenceLedger) -> EvidenceLedger:
    db.add(evidence)
    db.flush()
    return evidence


def list_evidence_by_metric(db: Session, metric_id: str) -> list[EvidenceLedger]:
    stmt = (
        select(EvidenceLedger)
        .where(EvidenceLedger.metric_id == metric_id)
        .order_by(EvidenceLedger.collected_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def list_evidence_by_metrics(
    db: Session, metric_ids: list[str]
) -> list[EvidenceLedger]:
    if not metric_ids:
        return []
    stmt = (
        select(EvidenceLedger)
        .where(EvidenceLedger.metric_id.in_(metric_ids))
        .order_by(EvidenceLedger.collected_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


# ── ExportRecord ─────────────────────────────────────────────
def create_export(db: Session, export: ExportRecord) -> ExportRecord:
    db.add(export)
    db.flush()
    return export


def get_export(db: Session, export_id: str) -> ExportRecord | None:
    return db.get(ExportRecord, export_id)


def update_export(db: Session, export: ExportRecord, **fields) -> ExportRecord:
    for key, value in fields.items():
        setattr(export, key, value)
    db.flush()
    return export


def list_exports_by_exporter(
    db: Session, exporter_id: str, limit: int = 50
) -> list[ExportRecord]:
    stmt = (
        select(ExportRecord)
        .where(ExportRecord.exporter_id == exporter_id)
        .order_by(ExportRecord.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())
