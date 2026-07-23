from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.submission import Submission
from app.models.user import User
from app.modules.evaluations.policy import ensure_can_manage_task_evaluations
from app.modules.evaluations.ai_grading import evaluate_submission, evaluate_submission_governed
from app.schemas.ai import (
    LessonPlanRequest,
    LessonPlanFromProjectRequest,
    AiProviderCreate,
    AiProviderUpdate,
    AiProviderResponse,
)
from app.schemas.lesson_plan import LessonPlanCreate, LessonPlanUpdate, LessonPlanResponse
from app.modules.lesson_plans.policy import (
    ensure_can_manage_lesson_plan,
    ensure_can_read_lesson_plan,
    lesson_plan_visibility_filter,
)
from app.modules.lesson_plans.service import (
    create_lesson_plan,
    delete_lesson_plan,
    get_lesson_plan,
    list_lesson_plans,
    update_lesson_plan,
)
from app.modules.ai_gateway.providers import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    test_provider_connection,
    update_provider,
)
from app.modules.lesson_plans.ai_generation import (
    generate_lesson_plan,
    generate_lesson_plan_from_project,
)

router = APIRouter(prefix="/ai", tags=["AI 智能"])


def _get_authorized_lesson_plan(
    db: Session,
    current_user: User,
    plan_id: str,
    *,
    manage: bool = False,
):
    lesson_plan = get_lesson_plan(db, plan_id)
    if not lesson_plan:
        raise AppException(code=40401, message="lesson plan not found", status_code=404)
    if manage:
        ensure_can_manage_lesson_plan(db, current_user, lesson_plan)
    else:
        ensure_can_read_lesson_plan(db, current_user, lesson_plan)
    return lesson_plan


@router.post("/lesson-plan", summary="AI 智能备课")
def lesson_plan_api(
    data: LessonPlanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["teacher", "school_admin"])),
):
    import asyncio
    result = asyncio.run(generate_lesson_plan(
        subject=data.subject, grade=data.grade, topic=data.topic,
        duration=data.duration, objectives=data.objectives,
        additional=data.additional, db=db,
    ))
    return success_response(data=result, message="教案生成成功")


@router.post("/lesson-plan/from-project", summary="基于项目结构化上下文 AI 备课")
def lesson_plan_from_project_api(
    data: LessonPlanFromProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """读取项目结构化上下文发起 AI 备课（计划 Task 5 验收标准 4）。

    不由页面重复录入学科/年级/主题；输入摘要自动从项目设计聚合。
    返回 AI 任务详情，含输出版本、质量问题和阻断问题数。
    """
    detail = generate_lesson_plan_from_project(db, current_user, data.project_id)
    return success_response(data=detail, message="教案生成成功")


def _mask_provider(p):
    d = AiProviderResponse.model_validate(p).model_dump()
    d["api_key"] = AiProviderResponse.mask_key(d["api_key"])
    return d


@router.get("/providers", summary="AI Provider 列表")
def list_providers_api(db: Session = Depends(get_db), _: User = Depends(require_roles(["admin", "school_admin"]))):
    items = list_providers(db)
    return success_response(data=[_mask_provider(p) for p in items])


@router.post("/providers", summary="创建 AI Provider")
def create_provider_api(data: AiProviderCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(["admin"]))):
    provider = create_provider(db, data)
    return success_response(data=_mask_provider(provider), message="创建成功")


@router.put("/providers/{provider_id}", summary="更新 AI Provider")
def update_provider_api(provider_id: str, data: AiProviderUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles(["admin"]))):
    try:
        provider = update_provider(db, provider_id, data)
    except ValueError as e:
        raise AppException(code=40401, message=str(e), status_code=404)
    return success_response(data=_mask_provider(provider), message="更新成功")


@router.delete("/providers/{provider_id}", summary="删除 AI Provider")
def delete_provider_api(provider_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(["admin"]))):
    ok = delete_provider(db, provider_id)
    if not ok:
        raise AppException(code=40401, message="Provider 不存在", status_code=404)
    return success_response(message="删除成功")


@router.post("/providers/{provider_id}/test", summary="测试 AI Provider 连接")
async def test_provider_api(provider_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles(["admin"]))):
    provider = get_provider(db, provider_id)
    if not provider:
        raise AppException(code=40401, message="Provider 不存在", status_code=404)
    ok = await test_provider_connection(provider.api_url, provider.api_key, provider.model)
    if ok:
        return success_response(message="连接成功")
    raise AppException(code=50001, message="连接失败，请检查配置", status_code=400)


@router.get("/lesson-plans", summary="我的教案列表")
def list_lesson_plans_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    items = list_lesson_plans(db, lesson_plan_visibility_filter(db, current_user))
    return success_response(data=[LessonPlanResponse.model_validate(p) for p in items])


@router.post("/lesson-plans", summary="保存教案")
def create_lesson_plan_api(
    data: LessonPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    plan = create_lesson_plan(db, data, current_user.id)
    return success_response(data=LessonPlanResponse.model_validate(plan), message="保存成功")


@router.get("/lesson-plans/{plan_id}", summary="获取教案")
def get_lesson_plan_api(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    plan = _get_authorized_lesson_plan(db, current_user, plan_id)
    if not plan:
        raise AppException(code=40401, message="教案不存在", status_code=404)
    return success_response(data=LessonPlanResponse.model_validate(plan))


@router.put("/lesson-plans/{plan_id}", summary="更新教案")
def update_lesson_plan_api(
    plan_id: str, data: LessonPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    plan = _get_authorized_lesson_plan(db, current_user, plan_id, manage=True)
    plan = update_lesson_plan(db, plan, data)
    if not plan:
        raise AppException(code=40401, message="教案不存在", status_code=404)
    return success_response(data=LessonPlanResponse.model_validate(plan), message="更新成功")


@router.delete("/lesson-plans/{plan_id}", summary="删除教案")
def delete_lesson_plan_api(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    plan = _get_authorized_lesson_plan(db, current_user, plan_id, manage=True)
    delete_lesson_plan(db, plan)
    ok = True
    if not ok:
        raise AppException(code=40401, message="教案不存在", status_code=404)
    return success_response(message="删除成功")


@router.post("/evaluate/batch", summary="AI 批量批改")
def evaluate_batch_api(
    task_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    ensure_can_manage_task_evaluations(db, current_user, task_id)
    from sqlalchemy import select
    stmt = select(Submission).where(
        Submission.task_id == task_id,
        Submission.status == "submitted",
    )
    subs = list(db.execute(stmt).scalars().all())
    results = []
    completed = 0
    for sub in subs:
        try:
            r = evaluate_submission(db, sub.id, current_user.id)
            succeeded = bool(r.get("evaluation_record_id"))
            results.append({"submission_id": sub.id, "success": succeeded, "result": r})
            if succeeded:
                completed += 1
        except Exception as e:
            results.append({"submission_id": sub.id, "success": False, "error": str(e)})
    return success_response(data={"total": len(subs), "completed": completed, "results": results})


@router.post("/evaluate/{submission_id}", summary="AI 批改单条提交")
def evaluate_single_api(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin"])),
):
    submission = db.get(Submission, submission_id)
    if submission:
        ensure_can_manage_task_evaluations(db, current_user, submission.task_id)
    try:
        result = evaluate_submission(db, submission_id, current_user.id)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    return success_response(data=result, message="AI 批改完成")


@router.post("/evaluate/{submission_id}/governed", summary="AI 批改（治理层：含版本与质量校验）")
def evaluate_governed_api(
    submission_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    """通过 AI 治理层评分（计划 Task 5）。

    创建 scene=GRADING 的 AI 任务，落库输出版本与质量问题，
    支持局部重生成与教师审核采用。失败不产生模拟分数。
    """
    submission = db.get(Submission, submission_id)
    if not submission:
        raise AppException(code=40401, message="提交记录不存在", status_code=404)
    ensure_can_manage_task_evaluations(db, current_user, submission.task_id)
    try:
        detail = evaluate_submission_governed(db, current_user, submission_id)
    except ValueError as e:
        raise AppException(code=40001, message=str(e), status_code=400)
    return success_response(data=detail, message="AI 批改任务已创建")
