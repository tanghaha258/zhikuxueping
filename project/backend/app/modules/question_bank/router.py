from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.response import error_response, success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.question_bank import policy, service
from app.schemas.question_bank import (
    AiGenerateRequest,
    BatchImportRequest,
    BatchImportResponse,
    QuestionCreate,
    QuestionQualityDetail,
    QuestionResponse,
    QuestionUpdate,
)


router = APIRouter(prefix="/question-bank", tags=["Question bank"])


@router.get("/questions", summary="List questions")
def list_questions_api(
    subject: str = Query(""), grade: str = Query(""), question_type: str = Query(""),
    difficulty_min: int = Query(0), difficulty_max: int = Query(5), knowledge_point: str = Query(""),
    keyword: str = Query(""), status: str = Query(""), source: str = Query(""),
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    items, total = service.list_questions(
        db, subject=subject, grade=grade, question_type=question_type, difficulty_min=difficulty_min,
        difficulty_max=difficulty_max, knowledge_point=knowledge_point, keyword=keyword, status=status,
        source=source, skip=skip, limit=limit, visibility_filter=policy.question_visibility_filter(current_user),
    )
    return success_response(data={"items": [QuestionResponse.model_validate(item).model_dump() for item in items], "total": total})


@router.post("/questions", summary="Create question")
def create_question_api(
    data: QuestionCreate, db: Session = Depends(get_db),
    user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.create_question(db, data, user.id)
    return success_response(data=QuestionResponse.model_validate(question).model_dump(), message="创建成功")


@router.get("/questions/{question_id}", summary="Get question")
def get_question_api(
    question_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.get_question(db, question_id)
    if not question:
        return error_response("题目不存在")
    policy.ensure_can_read_question(db, current_user, question)
    return success_response(data=QuestionResponse.model_validate(question).model_dump())


@router.put("/questions/{question_id}", summary="Update question")
def update_question_api(
    question_id: str, data: QuestionUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.get_question(db, question_id)
    if question:
        policy.ensure_can_manage_question(db, current_user, question)
    question = service.update_question(db, question_id, data)
    if not question:
        return error_response("题目不存在")
    return success_response(data=QuestionResponse.model_validate(question).model_dump(), message="更新成功")


@router.delete("/questions/{question_id}", summary="Delete question")
def delete_question_api(
    question_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.get_question(db, question_id)
    if question:
        policy.ensure_can_manage_question(db, current_user, question)
    if not service.delete_question(db, question_id):
        return error_response("题目不存在")
    return success_response(message="删除成功")


@router.post("/batch-import", summary="Batch import questions")
def batch_import_api(
    data: BatchImportRequest, db: Session = Depends(get_db),
    user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    imported, failed, errors = service.batch_import_questions(db, [item.model_dump() for item in data.questions], user.id)
    return success_response(
        data=BatchImportResponse(imported=imported, failed=failed, errors=errors).model_dump(),
        message=f"成功导入 {imported} 题，失败 {failed} 题",
    )


@router.post("/ai-generate", summary="Generate questions with AI")
def ai_generate_api(
    data: AiGenerateRequest, db: Session = Depends(get_db),
    user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    try:
        questions = service.ai_generate_questions(db, data, user.id)
        return success_response(
            data={"items": [QuestionResponse.model_validate(item).model_dump() for item in questions]},
            message=f"成功生成 {len(questions)} 道题目",
        )
    except ValueError as error:
        return error_response(message=str(error))
    except Exception as error:
        return error_response(message=f"AI 生成失败: {error}")


@router.get("/quality/stats", summary="Get question quality statistics")
def get_quality_stats_api(
    subject: str = Query(""), db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    return success_response(data=service.get_quality_stats(db, subject, policy.question_visibility_filter(current_user)))


@router.get("/questions/{question_id}/quality", summary="Get question quality")
def get_question_quality_api(
    question_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.get_question(db, question_id)
    if question:
        policy.ensure_can_read_question(db, current_user, question)
    detail = service.get_question_quality_detail(db, question_id)
    if detail is None:
        return error_response(message="题目不存在")
    return success_response(data=detail)


@router.put("/questions/{question_id}/quality", summary="Update question quality")
def update_question_quality_api(
    question_id: str, data: QuestionQualityDetail, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    question = service.get_question(db, question_id)
    if question:
        policy.ensure_can_manage_question(db, current_user, question)
    result = service.update_question_quality(db, question_id, data)
    if result is None:
        return error_response(message="题目不存在")
    return success_response(data=result, message="质量更新成功")
