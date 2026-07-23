from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.projects import service
from app.schemas.project import (
    ProjectCreate,
    ProjectReflectionRequest,
    ProjectReopenRequest,
    ProjectResponse,
    ProjectUpdate,
)


router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("", summary="项目列表")
def list_projects_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str = Query("", description="搜索标题"),
    status: str = Query("", description="筛选状态"),
    grade: str = Query("", description="筛选年级"),
    creator_id: str = Query("", description="筛选创建者"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.search_projects(
        db,
        current_user,
        keyword=keyword,
        status=status,
        grade=grade,
        creator_id=creator_id,
        skip=skip,
        limit=limit,
    )
    total = service.count_projects(
        db,
        current_user,
        keyword=keyword,
        status=status,
        grade=grade,
        creator_id=creator_id,
    )
    return success_response(
        data={
            "items": [_project_response(db, project) for project in items],
            "total": total,
            "page": skip // limit + 1,
            "page_size": limit,
        }
    )


@router.post("", summary="创建项目")
def create_project_api(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    project = service.create_project(db, current_user, data)
    return success_response(data=_project_response(db, project), message="创建成功")


@router.get("/{project_id}", summary="项目详情")
def get_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = service.get_project(db, current_user, project_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_project_response(db, project))


@router.get("/{project_id}/students", summary="项目关联班级的有效学生")
def list_project_students_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回项目关联班级中启用学生，用于任务分配选择（Task 1）。

    复用项目读权限策略；非项目教师、跨校管理员返回 403。
    字段：id / real_name / class_id / class_name。
    """
    students = service.list_project_students(db, current_user, project_id)
    return success_response(data=students)


@router.put("/{project_id}", summary="更新项目")
def update_project_api(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        project = service.update_project(db, current_user, project_id, data)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(data=_project_response(db, project), message="更新成功")


@router.delete("/{project_id}", summary="删除项目")
def delete_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    try:
        service.delete_project(db, current_user, project_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(message="删除成功")


@router.post("/{project_id}/submit-for-review", summary="提交项目审核（draft -> pending_review）")
def submit_for_review_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    """提交审核：草稿进入待审核状态。

    草稿允许暂缺字段（计划 3.4），完整性阻断在激活阶段强制；
    本接口仅做状态机校验，非法跃迁返回 409。
    """
    project = _transition(service.submit_for_review, db, current_user, project_id)
    return success_response(data=_project_response(db, project), message="项目已提交审核")


@router.post("/{project_id}/validate-activation", summary="校验项目是否可激活")
def validate_activation_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回 `blockers`、`warnings`、`completion` 和 `details`。

    不改变项目状态；供前端在激活前展示缺失项与完整度。
    读取权限即可调用（学生可见完整度但无法激活）。
    """
    try:
        result = service.validate_activation(db, current_user, project_id)
    except AppException:
        raise
    return success_response(data=result)


@router.post("/{project_id}/activate", summary="激活项目（pending_review -> active）")
def activate_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    project = _transition(service.activate_project, db, current_user, project_id)
    return success_response(data=_project_response(db, project), message="项目已激活")


@router.post("/{project_id}/complete", summary="完成项目")
def complete_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    project = _transition(service.complete_project, db, current_user, project_id)
    return success_response(data=_project_response(db, project), message="项目已完成")


@router.post("/{project_id}/archive", summary="归档项目")
def archive_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    project = _transition(service.archive_project, db, current_user, project_id)
    return success_response(data=_project_response(db, project), message="项目已归档")


# ============================================================
# 结项/归档扩展（Task 9）
# ============================================================

@router.post("/{project_id}/reopen", summary="重新开放归档项目（archived -> active，仅 school_admin）")
def reopen_project_api(
    project_id: str,
    data: ProjectReopenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["school_admin"])),
):
    """重新开放归档项目：仅学校管理员可调用，reason 必填且留痕。

    依据计划 Task 9 验收：重新开放必须授权并记录原因。
    普通教师/学生调用返回 403；reason 为空返回 400。
    """
    project = _transition(
        lambda d, a, pid: service.reopen_archived_project(d, a, pid, data.reason),
        db,
        current_user,
        project_id,
    )
    return success_response(data=_project_response(db, project), message="归档项目已重新开放")


@router.get("/{project_id}/closure-summary", summary="结项数据摘要")
def closure_summary_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回学生数/任务数/评价数/订正率/证据完整率/改进效果。

    依据计划 Task 9：结项数据摘要，不伪造数据。读取权限即可调用。
    """
    summary = service.get_closure_summary(db, current_user, project_id)
    return success_response(data=summary)


@router.post("/{project_id}/teacher-reflection", summary="保存教师结项反思")
def teacher_reflection_api(
    project_id: str,
    data: ProjectReflectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    """保存教师结项反思文本到项目字段。

    依据计划 Task 9：教师反思存入项目字段。归档项目禁止写操作（409）。
    """
    project = _transition(
        lambda d, a, pid: service.save_teacher_reflection(
            d, a, pid, data.reflection_text
        ),
        db,
        current_user,
        project_id,
    )
    return success_response(data=_project_response(db, project), message="教师反思已保存")


@router.get("/{project_id}/case-anonymization", summary="案例归档脱敏预览")
def case_anonymization_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回脱敏后的案例信息：学生姓名→编号、联系方式隐藏。

    依据计划 Task 9：案例归档脱敏预览，便于对外分享。读取权限即可调用。
    """
    preview = service.preview_case_anonymization(db, current_user, project_id)
    return success_response(data=preview)


def _project_response(db: Session, project) -> dict:
    data = ProjectResponse.model_validate(project).model_dump()
    data["subject_ids"] = service.get_project_subject_ids(db, project.id)
    data["class_ids"] = service.get_project_class_ids(db, project.id)
    return data


def _transition(operation, db: Session, current_user: User, project_id: str):
    try:
        return operation(db, current_user, project_id)
    except ValueError as error:
        raise AppException(code=40001, message=str(error), status_code=400) from error
