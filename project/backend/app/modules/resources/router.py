from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.resources import policy, service
from app.schemas.resource import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)


router = APIRouter(prefix="/resources", tags=["Resources"])


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
