"""资源服务层。

核心闭环扩展（计划 4.1/3.5/3.7）：
- `create_resource`/`update_resource` 支持层级、阶段、审核状态、来源等新字段。
- `validate_resource_tier_coverage` 返回三级递进覆盖检查结果。
- `list_resources_for_student` 学生侧仅返回已发布/已通过资源。

Task 8 扩展：资源与项目统一走工具上下文服务。
- `create_resource` 带 project_id 时自动建立一条默认引用（placement=resource）。
- `link_resource_to_project`/`unlink_resource_from_project` 通过 tool_context 服务
  管理引用；取消关联只删引用与 project_id 解耦，不删资产或文件。
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
from app.models.tool_context import ToolContextLink
from app.models.user import User
from app.modules.resources.repository import ResourceRepository
from app.modules.tool_context import service as tool_context_service
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
    _commit_and_refresh(db, resource)

    # Task 8：带 project_id 时自动建立一条默认项目引用（placement=resource）。
    # 授权已由 router 调用 policy.ensure_can_create_resource 保障，此处直接建引用。
    if data.project_id:
        _create_default_resource_link(db, resource, uploaded_by)

    return resource


def _create_default_resource_link(
    db: Session, resource: Resource, uploaded_by: str
) -> ToolContextLink | None:
    """为带项目的资源建立默认引用；已存在同位置引用时跳过（幂等）。"""
    from app.modules.tool_context.repository import ToolContextRepository

    repo = ToolContextRepository(db)
    existing = repo.find(
        artifact_type="resource",
        artifact_id=resource.id,
        project_id=resource.project_id,
        placement="resource",
    )
    if existing is not None:
        return existing
    link = ToolContextLink(
        artifact_type="resource",
        artifact_id=resource.id,
        project_id=resource.project_id,
        placement="resource",
        phase="preparation",
        created_by=uploaded_by,
    )
    repo.create(link)
    _commit(db)
    db.refresh(link)
    return link


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


# ── Task 8：工具上下文集成 ──────────────────────────────────────
def link_resource_to_project(
    db: Session,
    actor: User,
    resource_id: str,
    project_id: str,
    placement: str,
    *,
    phase: str | None = None,
    task_id: str | None = None,
    goal_id: str | None = None,
) -> ToolContextLink:
    """将资源关联到项目指定位置。

    复用 tool_context 服务完成授权、唯一性检查与引用创建。
    """
    resource = _require_resource(ResourceRepository(db), resource_id)
    return tool_context_service.link_asset(
        db,
        actor,
        artifact_type="resource",
        artifact_id=resource.id,
        project_id=project_id,
        placement=placement,
        phase=phase,
        task_id=task_id,
        goal_id=goal_id,
    )


def unlink_resource_from_project(db: Session, actor: User, link_id: str) -> dict:
    """取消资源与项目的关联：只删引用，不删资产或文件。

    若引用对应的是 resource 资产，同时清空 Resource.project_id 解耦项目关联，
    使资源回到独立状态；资产本体（标题/URL/文件大小等）保留。
    """
    result = tool_context_service.unlink_asset(db, actor, link_id)
    # 同步清空资源 project_id，避免遗留幽灵关联
    if result["artifact_type"] == "resource":
        resource = db.get(Resource, result["artifact_id"])
        if resource is not None:
            resource.project_id = None
            _commit(db)
    return result


def list_resource_links(
    db: Session, actor: User, resource_id: str
) -> list[ToolContextLink]:
    """列出一项资源的所有项目引用。"""
    resource = _require_resource(ResourceRepository(db), resource_id)
    return tool_context_service.list_artifact_links(
        db, actor, artifact_type="resource", artifact_id=resource.id
    )


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
