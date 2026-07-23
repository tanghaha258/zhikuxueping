"""AI 治理领域 API 路由（计划 Task 5）。

端点前缀：/api/v1/ai-jobs

覆盖：
- 创建并执行 AI 内容任务（同步）
- 任务列表与详情
- 状态机迁移（created -> queued -> running -> succeeded/failed -> reviewed -> adopted/rejected）
- 教师审核、采用/拒绝、局部重生成、失败重试
- 质量问题处理

设计要点：
- 备课输入由服务层读取项目结构化上下文，不由页面重复录入（验收标准 4）。
- 非法状态跃迁返回 409；Provider 不可用/超时/结构无效映射为失败，不产生伪成功。
- 阻断问题未处理不能标记正式版本（验收标准 6）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.enums import AiJobScene, AiJobStatus
from app.models.user import User
from app.modules.ai_jobs import service
from app.schemas.ai_job import (
    AiJobAdoptRequest,
    AiJobCreateRequest,
    AiJobRegenerateRequest,
    AiJobReviewRequest,
    AiJobTransitionRequest,
    QualityIssueResolveRequest,
)

router = APIRouter(prefix="/ai-jobs", tags=["AI 内容治理"])


# ── 创建并执行 AI 任务 ────────────────────────────────────────
@router.post("", summary="发起 AI 内容任务（携带项目上下文，同步执行）")
def create_job_api(
    data: AiJobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = service.create_and_run_job(
        db,
        current_user,
        data.project_id,
        data.scene,
        data.output_type,
        task_id=data.task_id,
        submission_id=data.submission_id,
    )
    return success_response(service.job_dict(job))


# ── 列表与详情 ───────────────────────────────────────────────
@router.get("", summary="AI 任务列表")
def list_jobs_api(
    project_id: str | None = Query(None, description="按项目过滤"),
    scene: AiJobScene | None = Query(None, description="按场景过滤"),
    status: AiJobStatus | None = Query(None, description="按状态过滤"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    jobs = service.list_jobs(
        db, current_user, project_id=project_id, scene=scene, status=status
    )
    return success_response(
        {
            "items": [service.job_dict(j) for j in jobs],
            "total": len(jobs),
        }
    )


@router.get("/{job_id}", summary="AI 任务详情（含全部版本与质量问题）")
def get_job_api(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    detail = service.get_job_detail(db, current_user, job_id)
    return success_response(detail)


# ── 状态机迁移 ───────────────────────────────────────────────
@router.post("/{job_id}/transition", summary="AI 任务状态机迁移")
def transition_job_api(
    job_id: str,
    data: AiJobTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = service.transition_job(db, current_user, job_id, data.target)
    return success_response(service.job_dict(job))


@router.post("/{job_id}/retry", summary="重试失败任务")
def retry_job_api(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = service.retry_job(db, current_user, job_id)
    return success_response(service.job_dict(job))


# ── 教师审核与采用 ───────────────────────────────────────────
@router.post("/{job_id}/review", summary="教师审核（标记 reviewed）")
def review_job_api(
    job_id: str,
    data: AiJobReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = service.review_job(db, current_user, job_id, data.note)
    return success_response(service.job_dict(job))


@router.post("/{job_id}/adopt", summary="教师采用/拒绝输出版本")
def adopt_job_api(
    job_id: str,
    data: AiJobAdoptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = service.adopt_job(
        db,
        current_user,
        job_id,
        data.version_id,
        data.adoption_status,
        data.note,
    )
    return success_response(service.job_dict(job))


@router.post("/{job_id}/regenerate", summary="局部重生成（创建新版本）")
def regenerate_job_api(
    job_id: str,
    data: AiJobRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version = service.regenerate_job(
        db,
        current_user,
        job_id,
        base_version_id=data.base_version_id,
        note=data.note,
    )
    return success_response(service.version_dict(version))


# ── 质量问题处理 ─────────────────────────────────────────────
@router.post("/quality-issues/{issue_id}/resolve", summary="处理质量问题")
def resolve_issue_api(
    issue_id: str,
    data: QualityIssueResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = service.resolve_issue(
        db, current_user, issue_id, data.resolution, data.status
    )
    return success_response(service.issue_dict(issue))
