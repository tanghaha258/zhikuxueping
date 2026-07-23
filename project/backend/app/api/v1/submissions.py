from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionUpdate, SubmissionResponse, SubmissionImportRequest
from app.modules.submissions.policy import (
    ensure_can_manage_submission,
    ensure_can_manage_task_submissions,
    ensure_can_read_submission,
    ensure_can_submit_to_task,
)
from app.modules.submissions.service import (
    bulk_import_submissions,
    create_submission,
    get_my_submission,
    get_submission,
    list_my_submissions,
    list_submissions_by_task,
    update_submission,
)

router = APIRouter(prefix="/submissions", tags=["任务提交"])


def _get_submission_or_404(db: Session, submission_id: str):
    submission = get_submission(db, submission_id)
    if not submission:
        raise AppException(code=40401, message="submission not found", status_code=404)
    return submission


@router.post("", summary="提交任务")
def submit_api(data: SubmissionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["student"]))):
    ensure_can_submit_to_task(db, current_user, data.task_id)
    sub = create_submission(db, data, student_id=current_user.id)
    return success_response(data=SubmissionResponse.model_validate(sub), message="提交成功")


@router.get("/my", summary="我提交的记录")
def my_submissions_api(db: Session = Depends(get_db), current_user: User = Depends(require_roles(["student"]))):
    items = list_my_submissions(db, current_user.id)
    return success_response(data=[SubmissionResponse.model_validate(s) for s in items])


@router.get("/task/{task_id}/my", summary="我针对某任务的提交")
def my_task_submission_api(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["student"]))):
    ensure_can_submit_to_task(db, current_user, task_id)
    sub = get_my_submission(db, task_id, current_user.id)
    if not sub:
        return success_response(data=None)
    return success_response(data=SubmissionResponse.model_validate(sub))


@router.get("/task/{task_id}", summary="任务的提交列表（教师用）")
def task_submissions_api(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"]))):
    ensure_can_manage_task_submissions(db, current_user, task_id)
    items = list_submissions_by_task(db, task_id)
    return success_response(data=[SubmissionResponse.model_validate(s) for s in items])


@router.get("/{submission_id}", summary="提交详情")
def get_submission_api(submission_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sub = _get_submission_or_404(db, submission_id)
    ensure_can_read_submission(db, current_user, sub)
    return success_response(data=SubmissionResponse.model_validate(sub))


@router.patch("/{submission_id}", summary="更新提交（评分）")
def update_submission_api(submission_id: str, data: SubmissionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"]))):
    sub = _get_submission_or_404(db, submission_id)
    ensure_can_manage_submission(db, current_user, sub)
    sub = update_submission(db, sub, data)
    return success_response(data=SubmissionResponse.model_validate(sub), message="更新成功")


@router.post("/import", summary="教师批量导入作业")
def import_submissions_api(
    data: SubmissionImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    ensure_can_manage_task_submissions(db, current_user, data.task_id)
    try:
        result = bulk_import_submissions(db, data.task_id, data.items)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    return success_response(data=result, message=f"成功导入 {result['imported']} 份作业")
