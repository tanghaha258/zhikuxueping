from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.papers.policy import (
    ensure_can_manage_paper,
    ensure_can_read_paper,
    paper_visibility_filter,
)
from app.schemas.paper import (
    PaperCreate, PaperUpdate, PaperResponse,
    AnswerKeyUpsert, AnswerKeyResponse,
    PaperSubmissionResponse, PaperStatsResponse,
)
from app.modules.papers.service import (
    create_paper, update_paper, get_paper, list_papers, count_papers, delete_paper,
    upsert_answer_key, get_answer_key,
    distribute_paper, list_submissions, get_paper_stats,
)
from app.modules.papers.ai_grading import evaluate_paper_submission
from app.modules.papers.feedback import process_grading_feedback

router = APIRouter(prefix="/papers", tags=["试卷批改"])


def _get_authorized_paper(
    db: Session,
    current_user: User,
    paper_id: str,
    *,
    manage: bool = False,
):
    paper = get_paper(db, paper_id)
    if not paper:
        raise AppException(code=40401, message="paper not found", status_code=404)
    if manage:
        ensure_can_manage_paper(db, current_user, paper)
    else:
        ensure_can_read_paper(db, current_user, paper)
    return paper


@router.get("", summary="试卷列表")
def list_papers_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    visibility_filter = paper_visibility_filter(db, current_user)
    items = list_papers(db, skip=skip, limit=limit, visibility_filter=visibility_filter)
    total = count_papers(db, visibility_filter=visibility_filter)
    return success_response(data={
        "items": [PaperResponse.model_validate(p).model_dump() for p in items],
        "total": total,
    })


@router.post("", summary="创建试卷")
def create_paper_api(
    data: PaperCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    paper = create_paper(db, data, teacher_id=current_user.id)
    return success_response(data=PaperResponse.model_validate(paper).model_dump(), message="创建成功")


@router.get("/{paper_id}", summary="试卷详情")
def get_paper_api(paper_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    paper = _get_authorized_paper(db, current_user, paper_id)
    return success_response(data=PaperResponse.model_validate(paper).model_dump())


@router.put("/{paper_id}", summary="更新试卷")
def update_paper_api(
    paper_id: str,
    data: PaperUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        paper = update_paper(db, paper_id, data)
    except ValueError as e:
        raise AppException(code=40401, message=str(e), status_code=404)
    return success_response(data=PaperResponse.model_validate(paper).model_dump(), message="更新成功")


@router.delete("/{paper_id}", summary="删除试卷")
def delete_paper_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    ok = delete_paper(db, paper_id)
    if not ok:
        raise AppException(code=40401, message="试卷不存在", status_code=404)
    return success_response(message="删除成功")


@router.post("/{paper_id}/answer-key", summary="设置答案与评分标准")
def set_answer_key_api(
    paper_id: str,
    data: AnswerKeyUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    ak = upsert_answer_key(db, paper_id, data)
    return success_response(data=AnswerKeyResponse.model_validate(ak).model_dump(), message="答案设置成功")


@router.get("/{paper_id}/answer-key", summary="获取答案与评分标准")
def get_answer_key_api(paper_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_authorized_paper(db, current_user, paper_id)
    ak = get_answer_key(db, paper_id)
    if not ak:
        raise AppException(code=40401, message="答案未设置", status_code=404)
    return success_response(data=AnswerKeyResponse.model_validate(ak).model_dump())


@router.post("/{paper_id}/distribute", summary="分发给班级学生")
def distribute_paper_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        count = distribute_paper(db, paper_id)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    return success_response(data={"distributed": count}, message=f"已分发 {count} 份答卷")


@router.get("/{paper_id}/submissions", summary="答卷列表")
def list_submissions_api(paper_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_authorized_paper(db, current_user, paper_id)
    items = list_submissions(db, paper_id)
    return success_response(data=[PaperSubmissionResponse.model_validate(s).model_dump() for s in items])


@router.get("/{paper_id}/stats", summary="批改统计")
def paper_stats_api(paper_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_authorized_paper(db, current_user, paper_id)
    stats = get_paper_stats(db, paper_id)
    return success_response(data=stats)


@router.post("/{paper_id}/evaluate", summary="AI 批改全部答卷")
def evaluate_paper_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    paper = _get_authorized_paper(db, current_user, paper_id, manage=True)
    ak = get_answer_key(db, paper_id)
    if not ak:
        raise AppException(code=40001, message="请先设置答案与评分标准", status_code=400)

    from app.models.paper import PaperStatus, SubmissionStatus
    subs = list_submissions(db, paper_id)
    pending = [s for s in subs if s.status == SubmissionStatus.PENDING]
    if not pending:
        return success_response(data={"total": 0, "completed": 0}, message="无待批改答卷")

    paper.status = PaperStatus.GRADING
    completed = 0
    for sub in pending:
        try:
            result = evaluate_paper_submission(db, sub, ak)
            if result.get("status") == "succeeded":
                completed += 1
        except Exception:
            continue

    # 仅当至少一份答卷被真实批改时才标记完成，避免伪造成功状态。
    paper.status = PaperStatus.DONE if completed > 0 else PaperStatus.PUBLISHED
    db.commit()
    return success_response(
        data={"total": len(pending), "completed": completed},
        message=f"批改完成：{completed}/{len(pending)}",
    )


@router.post("/{paper_id}/process-feedback", summary="批改反馈回流题库")
def process_feedback_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    result = process_grading_feedback(db, paper_id)
    if "error" in result:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"code": 40000, "message": result["error"], "data": None})
    db.commit()
    return success_response(data=result, message="反馈处理完成")


@router.post("/generate-smart", summary="学情驱动智能组卷（占位）")
def generate_smart_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success_response(data={"message": "学情驱动组卷功能即将上线"}, message="功能开发中")
