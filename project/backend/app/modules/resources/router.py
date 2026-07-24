from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.resources import policy, service
from app.modules.tool_context import service as tool_context_service
from app.schemas.resource import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)


router = APIRouter(prefix="/resources", tags=["Resources"])


# ── Task 8：工具上下文链接请求/响应模型 ──────────────────────────
class ContextLinkCreate(BaseModel):
    """关联资产到项目：项目模式必须提供 project_id 与 placement。

    project_id / placement 设为 Optional，缺值由 service 层校验返回 400
    （而非 Pydantic 422），以匹配 spec「项目模式必须 project_id+placement」
    的错误合同。
    """

    artifact_type: str
    artifact_id: str
    project_id: str | None = None
    placement: str | None = None
    phase: str | None = None
    task_id: str | None = None
    goal_id: str | None = None


class ContextLinkResponse(BaseModel):
    id: str
    artifact_type: str
    artifact_id: str
    project_id: str
    phase: str | None = None
    placement: str
    task_id: str | None = None
    goal_id: str | None = None
    context_snapshot: dict | None = None
    created_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ContextUnlinkResponse(BaseModel):
    artifact_type: str
    artifact_id: str
    preserved: bool


@router.get("", summary="List project resources")
def list_resources_api(
    project_id: str = Query(""),
    tier: str = Query("", description="按层级过滤: foundation/enhancement/extension"),
    stage: str = Query("", description="按教学阶段过滤: pre_class/in_class/post_class"),
    review_status: str = Query("", description="按审核状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not project_id:
        return success_response(data=[])
    policy.ensure_can_read_project_resources(db, current_user, project_id)
    # 学生仅可见已发布/已通过资源（计划 3.7）
    if policy.is_student(current_user):
        items = service.list_resources_for_student(db, project_id)
    else:
        items = service.list_resources_by_project(
            db,
            project_id,
            tier=tier or None,
            stage=stage or None,
            review_status=review_status or None,
        )
    return success_response(
        data=[ResourceResponse.model_validate(resource) for resource in items]
    )


@router.get("/tier-coverage", summary="Resource tier coverage check")
def tier_coverage_api(
    project_id: str = Query(..., description="项目 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """三级资源递进覆盖检查（计划 3.5.3）。

    返回每层是否至少有一项已发布资源、缺失层级与各层资源总数。
    """
    policy.ensure_can_read_project_resources(db, current_user, project_id)
    coverage = service.validate_resource_tier_coverage(db, project_id)
    return success_response(data=coverage)


@router.post("", summary="Create resource")
def create_resource_api(
    data: ResourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    policy.ensure_can_create_resource(db, current_user, data.project_id)
    resource = service.create_resource(db, data, uploaded_by=current_user.id)
    return success_response(
        data=ResourceResponse.model_validate(resource), message="Created successfully"
    )


# ============================================================
# Task 8：工具上下文链接端点
# 通用端点，支持 lesson_plan / resource / paper 等资产类型关联到项目。
# 项目模式必须 project_id + placement；跨校关联 403；取消关联只删引用不删资产。
# 注意：/context-links 路由必须注册在 /{resource_id} 之前，否则
# GET /context-links 会被 /{resource_id} 吞掉返回 404。
# ============================================================
@router.post("/context-links", summary="Link artifact to project context")
def create_context_link_api(
    data: ContextLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """关联独立工具资产到项目指定位置。

    - 项目模式必须提供 project_id 与 placement。
    - 跨校关联返回 403。
    - 同一资产在同一项目同一位置不可重复挂载（409）。
    """
    link = tool_context_service.link_asset(
        db,
        current_user,
        artifact_type=data.artifact_type,
        artifact_id=data.artifact_id,
        project_id=data.project_id,
        placement=data.placement,
        phase=data.phase,
        task_id=data.task_id,
        goal_id=data.goal_id,
    )
    return success_response(
        data=ContextLinkResponse.model_validate(link),
        message="Created successfully",
    )


@router.get("/context-links", summary="List context links")
def list_context_links_api(
    project_id: str = Query("", description="按项目过滤"),
    artifact_type: str = Query("", description="按资产类型过滤"),
    artifact_id: str = Query("", description="按资产 ID 过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出上下文引用。

    - 按 project_id 过滤：需要项目读权限（跨校 403）。
    - 按 artifact_type + artifact_id 过滤：列出该资产的所有项目引用。
    """
    if project_id:
        links = tool_context_service.list_project_links(
            db,
            current_user,
            project_id,
            artifact_type=artifact_type or None,
        )
    elif artifact_type and artifact_id:
        links = tool_context_service.list_artifact_links(
            db, current_user, artifact_type, artifact_id
        )
    else:
        return success_response(data=[])
    return success_response(
        data=[ContextLinkResponse.model_validate(link) for link in links]
    )


@router.delete("/context-links/{link_id}", summary="Unlink artifact from project")
def delete_context_link_api(
    link_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消关联：只删除引用，不删除资产本体或文件。

    若引用对应 resource 资产，同步清空 Resource.project_id 解耦项目关联。
    """
    result = service.unlink_resource_from_project(db, current_user, link_id)
    return success_response(
        data=ContextUnlinkResponse(**result), message="Unlinked successfully"
    )


@router.get("/{resource_id}", summary="Get resource")
def get_resource_api(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = service.get_resource(db, resource_id)
    policy.ensure_can_read_resource(db, current_user, resource)
    return success_response(data=ResourceResponse.model_validate(resource))


@router.put("/{resource_id}", summary="Update resource")
def update_resource_api(
    resource_id: str,
    data: ResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = service.get_resource(db, resource_id)
    policy.ensure_can_manage_resource(db, current_user, resource)
    resource = service.update_resource(db, resource_id, data)
    return success_response(
        data=ResourceResponse.model_validate(resource), message="Updated successfully"
    )


@router.delete("/{resource_id}", summary="Delete resource")
def delete_resource_api(
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resource = service.get_resource(db, resource_id)
    policy.ensure_can_manage_resource(db, current_user, resource)
    service.delete_resource(db, resource_id)
    return success_response(message="Deleted successfully")
