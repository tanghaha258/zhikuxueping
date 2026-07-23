"""学生端提交/订正/成长档案 API 路由（Task 6）。

端点前缀：/api/v1/student
（由主线程在 app/api/v1/__init__.py 注册：include_router(student_router)）

覆盖：
- 草稿保存与幂等提交（计划 3.7.3）
- 教师退回/最终确认（订正状态机）
- 学生二次评价请求（计划 3.7.4）
- 学生视角项目空间（计划 3.7.2）
- 学生视角反馈视图（计划 3.7.4）
- 成长档案（计划 3.7.5）

权限要点：
- 学生只能查看/操作自己的提交。
- 教师私有备注不返回给学生。
- 未发布评价不可见。
- 学生只能访问自己班级被分配的项目。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import Role, User
from app.modules.submissions import policy, service
from app.schemas.student_submission import (
    DraftSaveRequest,
    FinalizeSubmissionRequest,
    IdempotentSubmitRequest,
    ReassessRequest,
    ResubmitRequest,
    ReturnSubmissionRequest,
)

router = APIRouter(prefix="/student", tags=["学生空间"])


def _get_submission_or_404(db: Session, submission_id: str):
    submission = service.get_submission(db, submission_id)
    if not submission:
        raise AppException(code=40401, message="提交不存在", status_code=404)
    return submission


# ============================================================
# 草稿与提交（计划 3.7.3）
# ============================================================

@router.post("/drafts", summary="保存草稿（不创建版本）")
def save_draft_api(
    data: DraftSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student"])),
):
    policy.ensure_can_submit_to_task(db, current_user, data.task_id)
    submission = service.save_draft(
        db, data.task_id, current_user.id, data.content, data.file_urls
    )
    return success_response(
        data=policy.hide_submission_sensitive_fields(submission, current_user),
        message="草稿已保存",
    )


@router.post("/submissions", summary="幂等提交任务（重复点击不生成重复提交）")
def idempotent_submit_api(
    data: IdempotentSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student"])),
):
    policy.ensure_can_submit_to_task(db, current_user, data.task_id)
    submission, revision, created = service.submit_with_idempotency(
        db,
        data.task_id,
        current_user.id,
        data.content,
        data.file_urls,
        data.idempotency_key,
    )
    return success_response(
        data={
            "submission_id": submission.id,
            "revision_id": revision.id,
            "attempt_number": revision.attempt_number,
            "review_status": revision.review_status.value,
            "created": created,
        },
        message="提交成功" if created else "重复提交已忽略",
    )


@router.post("/submissions/{submission_id}/resubmit", summary="学生再提交（退回后再次提交）")
def resubmit_api(
    submission_id: str,
    data: ResubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student"])),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_can_resubmit(current_user, submission)
    # 再提交复用幂等提交流程
    _, revision, created = service.submit_with_idempotency(
        db,
        submission.task_id,
        current_user.id,
        data.content,
        data.file_urls,
        data.idempotency_key,
    )
    return success_response(
        data={
            "submission_id": submission.id,
            "revision_id": revision.id,
            "attempt_number": revision.attempt_number,
            "review_status": revision.review_status.value,
            "created": created,
        },
        message="再提交成功" if created else "重复提交已忽略",
    )


# ============================================================
# 教师退回/最终确认（订正状态机）
# ============================================================

@router.post("/submissions/{submission_id}/return", summary="教师退回提交")
def return_submission_api(
    submission_id: str,
    data: ReturnSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_can_manage_submission(db, current_user, submission)
    updated = service.return_submission(
        db,
        submission_id,
        teacher_comment=data.teacher_comment,
        teacher_private_note=data.teacher_private_note,
    )
    return success_response(
        data=policy.hide_submission_sensitive_fields(updated, current_user),
        message="已退回",
    )


@router.post("/submissions/{submission_id}/finalize", summary="教师最终确认提交")
def finalize_submission_api(
    submission_id: str,
    data: FinalizeSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_can_manage_submission(db, current_user, submission)
    updated = service.finalize_submission(
        db, submission_id, teacher_comment=data.teacher_comment
    )
    return success_response(
        data=policy.hide_submission_sensitive_fields(updated, current_user),
        message="已最终确认",
    )


# ============================================================
# 二次评价入口（计划 3.7.4）
# ============================================================

@router.post("/submissions/{submission_id}/reassess", summary="学生发起二次评价")
def request_reassessment_api(
    submission_id: str,
    data: ReassessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student"])),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_can_resubmit(current_user, submission)
    updated = service.request_reassessment(
        db, submission_id, current_user.id, data.reason
    )
    return success_response(
        data=policy.hide_submission_sensitive_fields(updated, current_user),
        message="二次评价请求已提交",
    )


# ============================================================
# 版本记录与反馈（计划 3.7.4）
# ============================================================

@router.get("/submissions/{submission_id}/revisions", summary="提交版本记录")
def list_revisions_api(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_student_can_read_submission(db, current_user, submission)
    revisions = service.list_revisions(db, submission_id)
    # 学生视角隐藏教师私有备注
    if current_user.role == Role.STUDENT:
        items = [service._revision_student_dict(r) for r in revisions]
    else:
        items = [service.revision_dict(r) for r in revisions]
    return success_response(data=items)


@router.get("/submissions/{submission_id}/feedback", summary="学生视角反馈视图")
def get_student_feedback_api(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(db, submission_id)
    policy.ensure_student_can_read_submission(db, current_user, submission)
    feedback = service.get_student_feedback(db, submission_id)
    return success_response(data=feedback)


# ============================================================
# 学生项目空间（计划 3.7.2）
# ============================================================

@router.get("/projects/{project_id}", summary="学生视角项目空间")
def get_student_project_api(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    policy.ensure_student_can_read_project(db, current_user, project_id)
    view = service.get_student_project_view(
        db, project_id, current_user.class_id
    )
    return success_response(data=view)


# ============================================================
# 成长档案（计划 3.7.5）
# ============================================================

@router.get("/growth", summary="成长档案")
def get_growth_portfolio_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["student"])),
):
    portfolio = service.get_growth_portfolio(db, current_user.id)
    return success_response(data=portfolio)
