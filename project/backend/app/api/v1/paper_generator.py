import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.models.paper_template import PaperTemplate
from app.models.knowledge_point import KnowledgePoint
from fastapi.responses import StreamingResponse
from app.modules.paper_generation.policy import ensure_can_manage_paper, ensure_can_read_paper
from app.modules.paper_generation.formatting import (
    format_paper,
    get_formatted_paper,
    update_formatted_paper,
)
from app.modules.paper_generation.exporting import export_paper
from app.modules.paper_generation.papers import (
    count_generated_papers,
    delete_generated_paper,
    finalize_paper,
    get_generated_paper,
    list_generated_papers,
    update_generated_paper,
)
from app.modules.paper_generation.templates import (
    count_templates,
    create_template,
    delete_template,
    get_template,
    list_templates,
    sync_template_to_teacher,
    update_template,
)
from app.modules.question_bank.policy import question_visibility_filter
from app.schemas.paper_generator import (
    PaperTemplateCreate, PaperTemplateUpdate, PaperTemplateResponse,
    GeneratePaperRequest, GeneratePaperGovernedRequest, AiGeneratedPaperUpdate, AiGeneratedPaperResponse,
    GeneratePaperResponse, FormatRequest,
    KnowledgePointCreate, KnowledgePointResponse,
)
from app.schemas.question_bank import SmartComposeRequest
from app.modules.paper_generation.generation import (
    _call_ai_generate_stream,
    count_section_total,
    generate_paper,
    generate_paper_governed,
    get_default_sections,
    smart_compose_paper,
)


def _get_authorized_paper(
    db: Session,
    current_user: User,
    paper_id: str,
    *,
    manage: bool = False,
):
    paper = get_generated_paper(db, paper_id)
    if not paper:
        raise AppException(code=40401, message="paper not found", status_code=404)
    if manage:
        ensure_can_manage_paper(db, current_user, paper)
    else:
        ensure_can_read_paper(db, current_user, paper)
    return paper

router = APIRouter(prefix="/paper-generator", tags=["AI 出卷"])


# ── Templates ──

@router.get("/templates", summary="模板列表")
def list_templates_api(
    subject: str = Query("", description="学科过滤"),
    grade: str = Query("", description="年级过滤"),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(PaperTemplate).where(PaperTemplate.is_active == True)
    if subject:
        q = q.where(PaperTemplate.subject == subject)
    if grade:
        q = q.where(PaperTemplate.grade == grade)
    q = q.order_by(PaperTemplate.created_at.desc()).offset(skip).limit(limit)
    items = list(db.execute(q).scalars().all())
    total_q = select(func.count()).select_from(PaperTemplate).where(PaperTemplate.is_active == True)
    if subject:
        total_q = total_q.where(PaperTemplate.subject == subject)
    if grade:
        total_q = total_q.where(PaperTemplate.grade == grade)
    total = db.execute(total_q).scalar() or 0
    return success_response(data={
        "items": [PaperTemplateResponse.model_validate(t).model_dump() for t in items],
        "total": total,
    })


@router.post("/templates", summary="创建模板")
def create_template_api(
    data: PaperTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin", "school_admin"])),
):
    try:
        tpl = create_template(db, data)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    return success_response(data=PaperTemplateResponse.model_validate(tpl).model_dump(), message="创建成功")


@router.get("/templates/{template_id}", summary="模板详情")
def get_template_api(template_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    tpl = get_template(db, template_id)
    if not tpl:
        raise AppException(code=40401, message="模板不存在", status_code=404)
    return success_response(data=PaperTemplateResponse.model_validate(tpl).model_dump())


@router.put("/templates/{template_id}", summary="更新模板")
def update_template_api(
    template_id: str, data: PaperTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin", "school_admin"])),
):
    try:
        tpl = update_template(db, template_id, data)
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg:
            raise AppException(code=40401, message="模板不存在", status_code=404)
        raise AppException(code=40001, message=msg, status_code=400)
    return success_response(data=PaperTemplateResponse.model_validate(tpl).model_dump(), message="更新成功")


@router.delete("/templates/{template_id}", summary="删除模板")
def delete_template_api(
    template_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin", "school_admin"])),
):
    ok = delete_template(db, template_id)
    if not ok:
        raise AppException(code=40401, message="模板不存在", status_code=404)
    return success_response(message="删除成功")


@router.post("/templates/{template_id}/sync", summary="教师同步模板")
def sync_template_api(
    template_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin", "teacher"])),
):
    try:
        tpl = sync_template_to_teacher(db, template_id, current_user.id)
    except ValueError:
        raise AppException(code=40401, message="模板不存在", status_code=404)
    return success_response(
        data=PaperTemplateResponse.model_validate(tpl).model_dump(),
        message="同步成功",
    )


# ── Generate ──

@router.post("/generate", summary="AI 生成试卷")
def generate_paper_api(
    data: GeneratePaperRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    paper, warning = generate_paper(
        db, teacher_id=current_user.id,
        subject=data.subject, grade=data.grade,
        difficulty=data.difficulty,
        template_id=data.template_id,
        title=data.title,
        knowledge_points=data.knowledge_points,
        sections=data.sections,
        exam_type=data.exam_type or "quiz",
    )
    return success_response(
        data=GeneratePaperResponse(
            id=paper.id, title=paper.title,
            questions=paper.questions or "[]",
            total_score=paper.total_score,
            duration=paper.duration,
            difficulty=paper.difficulty,
            template_id=paper.template_id,
            status=paper.status,
            warning=warning,
        ).model_dump(),
        message="生成成功" if not warning else f"生成成功，{warning}",
    )


@router.post("/generate-governed", summary="治理层出卷（含版本与质量校验）")
def generate_paper_governed_api(
    data: GeneratePaperGovernedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """通过 AI 治理层出卷（计划 Task 5）。

    读取项目结构化上下文作为输入摘要，创建 scene=PAPER 的 AI 任务。
    不使用模拟数据：Provider 不可用/超时/结构无效均映射为 FAILED。
    返回 AI 任务详情（含版本、质量问题、阻断问题数）。
    """
    detail = generate_paper_governed(
        db, current_user, data.project_id, output_type=data.output_type
    )
    return success_response(data=detail, message="出卷任务已创建")


@router.post("/smart-compose", summary="智能组卷（题库+AI混合）")
def smart_compose_api(
    data: SmartComposeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    try:
        paper, warning = smart_compose_paper(
            db, teacher_id=current_user.id,
            subject=data.subject, grade=data.grade,
            difficulty=data.difficulty,
            template_id=data.template_id,
            knowledge_points=data.knowledge_points,
            sections=data.sections,
            total_score=data.total_score,
            bank_ratio=data.bank_ratio,
            exam_type="quiz",
            question_visibility=question_visibility_filter(current_user),
        )
    except ValueError as exc:
        raise AppException(code=40001, message=str(exc), status_code=400)
    return success_response(
        data=GeneratePaperResponse(
            id=paper.id, title=paper.title,
            questions=paper.questions or "[]",
            total_score=paper.total_score,
            duration=paper.duration,
            difficulty=paper.difficulty,
            template_id=paper.template_id,
            status=paper.status,
            warning=warning,
        ).model_dump(),
        message="组卷成功" if not warning else f"组卷成功，{warning}",
    )


# ── Generated Papers ──

@router.get("/papers", summary="已生成试卷列表")
def list_papers_api(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    teacher_id = current_user.id if current_user.role in ("teacher",) else ""
    items = list_generated_papers(db, teacher_id, skip, limit) if teacher_id else []
    total = count_generated_papers(db, teacher_id) if teacher_id else 0
    return success_response(data={
        "items": [AiGeneratedPaperResponse.model_validate(p).model_dump() for p in items],
        "total": total,
    })


@router.get("/papers/{paper_id}", summary="试卷详情")
def get_paper_api(paper_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    paper = _get_authorized_paper(db, current_user, paper_id)
    if not paper:
        raise AppException(code=40401, message="试卷不存在", status_code=404)
    return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump())


@router.put("/papers/{paper_id}", summary="编辑试卷")
def update_paper_api(
    paper_id: str, data: AiGeneratedPaperUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        paper = update_generated_paper(db, paper_id, data)
    except ValueError:
        raise AppException(code=40401, message="试卷不存在", status_code=404)
    return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump(), message="更新成功")


@router.post("/papers/{paper_id}/finalize", summary="定稿")
def finalize_paper_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        paper = finalize_paper(db, paper_id)
    except ValueError:
        raise AppException(code=40401, message="试卷不存在", status_code=404)
    return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump(), message="已定稿")


@router.post("/papers/{paper_id}/export", summary="导出试卷")
def export_paper_api(
    paper_id: str,
    fmt: str = Query("html", alias="format", pattern="^(html|word|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id)
    try:
        content = export_paper(db, paper_id, fmt)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    from fastapi.responses import HTMLResponse
    if fmt == "html":
        return HTMLResponse(content=content)
    return success_response(data={"content": content}, message="导出成功")


@router.delete("/papers/{paper_id}", summary="删除试卷")
def delete_paper_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    ok = delete_generated_paper(db, paper_id)
    if not ok:
        raise AppException(code=40401, message="试卷不存在", status_code=404)
    return success_response(message="删除成功")


# ── Format ──


@router.post("/papers/{paper_id}/format", summary="试卷转换")
def format_paper_api(
    paper_id: str, data: FormatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        paper = format_paper(db, paper_id, data.template_type, data.subject)
        return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump())
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)


@router.get("/papers/{paper_id}/formatted", summary="获取格式化试卷")
def get_formatted_api(
    paper_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id)
    paper = get_formatted_paper(db, paper_id)
    if not paper:
        raise AppException(code=40401, message="试卷不存在或未格式化", status_code=404)
    return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump())


@router.put("/papers/{paper_id}/formatted", summary="更新格式化试卷（富文本编辑保存）")
def update_formatted_api(
    paper_id: str, data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    _get_authorized_paper(db, current_user, paper_id, manage=True)
    try:
        paper = update_formatted_paper(
            db, paper_id,
            data.get("formatted_html", ""),
            data.get("template_config"),
        )
        return success_response(data=AiGeneratedPaperResponse.model_validate(paper).model_dump())
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)


# ── Streaming ──


@router.post("/generate-stream", summary="流式 AI 出卷")
async def generate_paper_stream_api(
    data: GeneratePaperRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    from app.models.ai_provider import AiProvider
    from sqlalchemy import select
    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()

    async def event_stream():
        seen_count = 0
        all_questions = []
        ai_data = {}
        saved_paper_id = ""
        try:
            async for event in _call_ai_generate_stream(
                data.subject, data.grade, data.difficulty,
                data.knowledge_points, data.sections, data.exam_type or "quiz",
                api_url=provider.api_url if provider else None,
                api_key=provider.api_key if provider else None,
                model=provider.model if provider else None,
                db=db,
            ):
                if event["type"] == "question":
                    seen_count += 1
                    all_questions.append(event["data"])
                    yield f"data: {json.dumps({'type': 'question', 'index': seen_count, 'data': event['data']})}\n\n"
                elif event["type"] == "done":
                    ai_data = event["data"] or {}
                    saved_paper_id = ""
                    try:
                        from app.db.session import SessionLocal
                        from app.models.paper_template import AiGeneratedPaper as AGP
                        save_db = SessionLocal()
                        try:
                            title_val = (ai_data.get("title") if isinstance(ai_data, dict) else None) or data.title or f"{data.grade}年级{data.subject}测试卷"
                            q_save = (ai_data.get("questions") if isinstance(ai_data, dict) else None) or all_questions
                            kp_val = data.knowledge_points or []
                            res_sec = data.sections
                            if not res_sec and data.template_id:
                                tpl = get_template(save_db, data.template_id)
                                if tpl and tpl.sections:
                                    res_sec = tpl.sections
                            if not res_sec:
                                res_sec = get_default_sections(data.exam_type or "quiz", data.subject)
                            ts = count_section_total(res_sec) if res_sec else 100.0
                            dur = (ai_data.get("duration", 90) if isinstance(ai_data, dict) else 90)
                            paper = AGP(
                                teacher_id=user.id,
                                template_id=data.template_id,
                                subject=data.subject,
                                grade=data.grade,
                                title=title_val,
                                difficulty=data.difficulty,
                                knowledge_points=json.dumps(kp_val, ensure_ascii=False),
                                questions=json.dumps(q_save, ensure_ascii=False),
                                total_score=ts,
                                duration=dur,
                                status="draft",
                            )
                            save_db.add(paper)
                            save_db.commit()
                            save_db.refresh(paper)
                            saved_paper_id = paper.id
                        finally:
                            save_db.close()
                    except Exception:
                        pass
                    done_payload = {"title": ai_data.get("title", "") if isinstance(ai_data, dict) else "", "questions": ai_data.get("questions", []) if isinstance(ai_data, dict) else [], "total_score": ai_data.get("total_score", 100) if isinstance(ai_data, dict) else 100, "duration": ai_data.get("duration", 90) if isinstance(ai_data, dict) else 90}
                    if saved_paper_id:
                        done_payload["id"] = saved_paper_id
                    yield f"data: {json.dumps({'type': 'done', 'total': seen_count, 'data': done_payload})}\n\n"
                elif event["type"] == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': event['message']})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Knowledge Points ──


@router.get("/knowledge-points", summary="知识点列表")
def list_knowledge_points_api(
    subject: str = Query("", description="学科代码, 空=全部"),
    grade: str = Query("", description="年级, 空=全部"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    filters = {}
    if subject:
        filters["subject"] = subject
    if grade:
        filters["grade"] = grade
    items = db.query(KnowledgePoint).filter_by(**filters).order_by(
        KnowledgePoint.subject, KnowledgePoint.sort_order
    ).all()
    return success_response(data=[KnowledgePointResponse.model_validate(k).model_dump() for k in items])


@router.post("/knowledge-points", summary="创建知识点")
def create_knowledge_point_api(
    data: KnowledgePointCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin", "school_admin"])),
):
    kp = KnowledgePoint(**data.model_dump())
    db.add(kp)
    db.commit()
    db.refresh(kp)
    return success_response(data=KnowledgePointResponse.model_validate(kp).model_dump(), message="创建成功")
