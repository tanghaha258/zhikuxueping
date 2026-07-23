"""运营证据领域 API 路由（Task 8）。

端点前缀：/api/v1/operational-evidence

覆盖：
- 运营指标列表/详情（含公式/周期/样本量/来源/责任人，验收 3.8.3）
- 证据台账登记与查询
- 导出预览（含脱敏）/ 二次确认 / 审计记录查询
- 真实/测试/演示/导入数据过滤（默认 data_origin=real）

设计要点：
- 仅管理员可访问；学校管理员只能访问本校范围。
- 默认仅返回真实数据，避免测试/演示/导入数据污染指标。
- 导出必须经过预览->二次确认，且每次导出落审计记录。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.response import success_response
from app.db.session import get_db
from app.models.enums import DataOrigin
from app.models.operational_evidence import OperationalMetricPeriod
from app.models.user import User
from app.modules.operational_evidence import service
from app.schemas.operational_evidence import (
    EvidenceLedgerCreateRequest,
    ExportConfirmRequest,
    ExportPreviewRequest,
    OperationalMetricCreateRequest,
)

router = APIRouter(
    prefix="/operational-evidence",
    tags=["运营证据"],
)


# ── 运营指标 ──────────────────────────────────────────────────
@router.get("/metrics", summary="运营指标列表（默认仅真实数据）")
def list_metrics_api(
    data_origin: DataOrigin | None = Query(
        DataOrigin.REAL, description="数据来源过滤，默认仅 real"
    ),
    school_id: str | None = Query(None, description="按学校过滤（系统管理员）"),
    period: OperationalMetricPeriod | None = Query(None, description="按周期过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    metrics = service.list_metrics(
        db,
        current_user,
        data_origin=data_origin,
        school_id=school_id,
        period=period.value if period else None,
    )
    return success_response(
        {
            "items": [service.metric_dict(m) for m in metrics],
            "total": len(metrics),
        }
    )


@router.get("/metrics/{metric_id}", summary="运营指标详情（含公式/周期/样本量/来源/责任人 + 证据台账）")
def get_metric_api(
    metric_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    detail = service.get_metric_detail(db, current_user, metric_id)
    return success_response(detail)


@router.post("/metrics", summary="登记运营指标")
def create_metric_api(
    data: OperationalMetricCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    metric = service.create_metric(
        db,
        current_user,
        name=data.name,
        code=data.code,
        formula=data.formula,
        period=data.period,
        sample_size=data.sample_size,
        source_table=data.source_table,
        source_owner=data.source_owner,
        responsible_person=data.responsible_person,
        data_origin=data.data_origin,
        value=data.value,
        value_collected_at=data.value_collected_at,
        school_id=data.school_id,
    )
    return success_response(service.metric_dict(metric))


# ── 证据台账 ──────────────────────────────────────────────────
@router.get("/metrics/{metric_id}/evidence", summary="指标证据台账")
def list_evidence_api(
    metric_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    evidence = service.list_evidence(db, current_user, metric_id)
    return success_response(
        {
            "items": [service.evidence_dict(e) for e in evidence],
            "total": len(evidence),
        }
    )


@router.post("/metrics/{metric_id}/evidence", summary="登记证据台账")
def register_evidence_api(
    metric_id: str,
    data: EvidenceLedgerCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    # 忽略路径与请求体中 metric_id 不一致的情况，统一以路径为准
    evidence = service.register_evidence(
        db,
        current_user,
        metric_id=metric_id,
        evidence_ref=data.evidence_ref,
        evidence_summary=data.evidence_summary,
        collected_at=data.collected_at,
    )
    return success_response(service.evidence_dict(evidence))


# ── 导出预览/二次确认/审计 ─────────────────────────────────────
@router.post("/exports/preview", summary="导出预览（脱敏 + 落 PREVIEWED 审计记录）")
def preview_export_api(
    data: ExportPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    result = service.preview_export(
        db,
        current_user,
        metric_ids=data.metric_ids,
        anonymized=data.anonymized,
        school_id=data.school_id,
    )
    return success_response(result)


@router.post("/exports/confirm", summary="导出二次确认（仅 PREVIEWED 可确认）")
def confirm_export_api(
    data: ExportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    export = service.confirm_export(
        db, current_user, export_id=data.export_id, audit_note=data.audit_note
    )
    return success_response(service.export_dict(export))


@router.get("/exports", summary="导出审计记录（仅本人发起）")
def list_exports_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    exports = service.list_export_records(db, current_user)
    return success_response(
        {
            "items": [service.export_dict(e) for e in exports],
            "total": len(exports),
        }
    )
