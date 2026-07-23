"""资源服务层。

核心闭环扩展（计划 4.1/3.5/3.7）：
- `create_resource`/`update_resource` 支持层级、阶段、审核状态、来源等新字段。
- `validate_resource_tier_coverage` 返回三级递进覆盖检查结果。
- `list_resources_for_student` 学生侧仅返回已发布/已通过资源。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.enums import (
    ResourceSourceType,
    ResourceTier,
    ReviewStatus,
    TeachingStage,
)
from app.models.resource import Resource
from app.modules.resources.repository import ResourceRepository
from app.schemas.resource import (
    ResourceCreate,
    ResourceTierCoverage,
    ResourceUpdate,
)


def list_resources_by_project(
    db: Session,
    project_id: str,
    *,
    tier: str | None = None,
    stage: str | None = None,
    review_status: str | None = None,
) -> list[Resource]:
    return ResourceRepository(db).list_by_project(
        project_id, tier=tier, stage=stage, review_status=review_status
    )


def list_resources_for_student(db: Session, project_id: str) -> list[Resource]:
    """学生侧资源列表：仅返回已发布/已通过资源（计划 3.7）。"""
    return ResourceRepository(db).list_published_for_student(project_id)


def get_resource(db: Session, resource_id: str) -> Resource:
    return _require_resource(ResourceRepository(db), resource_id)


def create_resource(db: Session, data: ResourceCreate, uploaded_by: str) -> Resource:
    resource = Resource(
        project_id=data.project_id,
        title=data.title,
        res_type=data.res_type,
        url=data.url,
        file_size=data.file_size,
        uploaded_by=uploaded_by,
        tier=_parse_tier(data.tier),
        stage=_parse_stage(data.stage),
        cognitive_level=data.cognitive_level,
        reading_level=data.reading_level,
        prerequisites=data.prerequisites,
        review_status=_parse_review_status(data.review_status) or ReviewStatus.DRAFT,
        source_type=_parse_source_type(data.source_type),
        source_ref=data.source_ref,
        usage_tip=data.usage_tip,
    )
    ResourceRepository(db).add(resource)
    return _commit_and_refresh(db, resource)


def update_resource(db: Session, resource_id: str, data: ResourceUpdate) -> Resource:
    resource = _require_resource(ResourceRepository(db), resource_id)
    updates = data.model_dump(exclude_unset=True)
    # 枚举字段需转换为枚举实例，避免直接 setattr 字符串导致类型不一致。
    if "tier" in updates:
        resource.tier = _parse_tier(updates.pop("tier"))
    if "stage" in updates:
        resource.stage = _parse_stage(updates.pop("stage"))
    if "review_status" in updates:
        parsed = _parse_review_status(updates.pop("review_status"))
        if parsed is not None:
            resource.review_status = parsed
    if "source_type" in updates:
        resource.source_type = _parse_source_type(updates.pop("source_type"))
    for field, value in updates.items():
        setattr(resource, field, value)
    return _commit_and_refresh(db, resource)


def delete_resource(db: Session, resource_id: str) -> None:
    repository = ResourceRepository(db)
    resource = _require_resource(repository, resource_id)
    repository.delete(resource)
    _commit(db)


def validate_resource_tier_coverage(
    db: Session, project_id: str
) -> ResourceTierCoverage:
    """三级资源递进覆盖检查（计划 3.5.3）。

    每层至少一项已发布（PUBLISHED）资源才算覆盖；`missing` 列出缺失层级。
    `counts` 统计各层资源总数（含未分层 unassigned），便于教师查看分布。
    `total` 为该项目资源总数。
    """
    repository = ResourceRepository(db)
    published = repository.count_published_by_tier(project_id)
    total_rows = repository.count_by_tier(project_id)
    has_foundation = published["foundation"] > 0
    has_enhancement = published["enhancement"] > 0
    has_extension = published["extension"] > 0
    missing: list[str] = []
    if not has_foundation:
        missing.append("foundation")
    if not has_enhancement:
        missing.append("enhancement")
    if not has_extension:
        missing.append("extension")
    total = sum(total_rows.values())
    return ResourceTierCoverage(
        foundation=has_foundation,
        enhancement=has_enhancement,
        extension=has_extension,
        counts={
            "foundation": total_rows["foundation"],
            "enhancement": total_rows["enhancement"],
            "extension": total_rows["extension"],
            "unassigned": total_rows["unassigned"],
        },
        missing=missing,
        total=total,
    )


# ── 枚举解析辅助 ──────────────────────────────────────────
def _parse_tier(value: str | None) -> ResourceTier | None:
    if value is None or value == "":
        return None
    try:
        return ResourceTier(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的资源层级: {value}", status_code=400
        )


def _parse_stage(value: str | None) -> TeachingStage | None:
    if value is None or value == "":
        return None
    try:
        return TeachingStage(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的教学阶段: {value}", status_code=400
        )


def _parse_review_status(value: str | None) -> ReviewStatus | None:
    if value is None or value == "":
        return None
    try:
        return ReviewStatus(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的审核状态: {value}", status_code=400
        )


def _parse_source_type(value: str | None) -> ResourceSourceType | None:
    if value is None or value == "":
        return None
    try:
        return ResourceSourceType(value)
    except ValueError:
        raise AppException(
            code=40002, message=f"无效的资源来源类型: {value}", status_code=400
        )


def _require_resource(repository: ResourceRepository, resource_id: str) -> Resource:
    resource = repository.get(resource_id)
    if not resource:
        raise AppException(code=40401, message="Resource not found", status_code=404)
    return resource


def _commit_and_refresh(db: Session, record: Resource) -> Resource:
    _commit(db)
    db.refresh(record)
    return record


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
