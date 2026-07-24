"""教案服务层。

Task 8 扩展：教案与项目统一走工具上下文服务。
- ``link_lesson_plan_to_project``/``unlink_lesson_plan_from_project`` 通过
  tool_context 服务管理引用；取消关联只删引用，教案资产保留。
- ``list_lesson_plan_links`` 列出教案的所有项目引用。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.saved_lesson_plan import SavedLessonPlan
from app.models.tool_context import ToolContextLink
from app.models.user import User
from app.modules.lesson_plans.policy import ensure_can_manage_lesson_plan
from app.modules.tool_context import service as tool_context_service
from app.schemas.lesson_plan import LessonPlanCreate, LessonPlanUpdate


def list_lesson_plans(db: Session, visibility_filter) -> list[SavedLessonPlan]:
    statement = (
        select(SavedLessonPlan)
        .where(visibility_filter)
        .order_by(SavedLessonPlan.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def create_lesson_plan(
    db: Session,
    data: LessonPlanCreate,
    user_id: str,
) -> SavedLessonPlan:
    lesson_plan = SavedLessonPlan(
        user_id=user_id,
        title=data.title,
        content=data.content,
        subject=data.subject,
        grade=data.grade,
        topic=data.topic,
        duration=data.duration,
    )
    db.add(lesson_plan)
    db.commit()
    db.refresh(lesson_plan)
    return lesson_plan


def get_lesson_plan(db: Session, plan_id: str) -> SavedLessonPlan | None:
    return db.get(SavedLessonPlan, plan_id)


def update_lesson_plan(
    db: Session,
    lesson_plan: SavedLessonPlan,
    data: LessonPlanUpdate,
) -> SavedLessonPlan:
    if data.title is not None:
        lesson_plan.title = data.title
    if data.content is not None:
        lesson_plan.content = data.content
    db.commit()
    db.refresh(lesson_plan)
    return lesson_plan


def delete_lesson_plan(db: Session, lesson_plan: SavedLessonPlan) -> None:
    db.delete(lesson_plan)
    db.commit()


# ============================================================
# Task 8：工具上下文集成
# 教案作为独立资产存在；关联到项目时只创建引用，不复制内容。
# 取消关联只删引用，教案本体（标题/内容/学科等）保留。
# ============================================================
def link_lesson_plan_to_project(
    db: Session,
    actor: User,
    plan_id: str,
    project_id: str,
    placement: str,
    *,
    phase: str | None = None,
    task_id: str | None = None,
    goal_id: str | None = None,
) -> ToolContextLink:
    """将教案关联到项目指定位置。

    先校验教案可见性（教师本人或同校管理员），再复用 tool_context 服务
    完成项目授权、唯一性检查与引用创建。
    """
    plan = _require_lesson_plan(db, plan_id)
    ensure_can_manage_lesson_plan(db, actor, plan)
    return tool_context_service.link_asset(
        db,
        actor,
        artifact_type="lesson_plan",
        artifact_id=plan.id,
        project_id=project_id,
        placement=placement,
        phase=phase,
        task_id=task_id,
        goal_id=goal_id,
    )


def unlink_lesson_plan_from_project(db: Session, actor: User, link_id: str) -> dict:
    """取消教案与项目的关联：只删引用，不删教案资产。"""
    return tool_context_service.unlink_asset(db, actor, link_id)


def list_lesson_plan_links(
    db: Session, actor: User, plan_id: str
) -> list[ToolContextLink]:
    """列出一项教案的所有项目引用。"""
    plan = _require_lesson_plan(db, plan_id)
    ensure_can_manage_lesson_plan(db, actor, plan)
    return tool_context_service.list_artifact_links(
        db, actor, artifact_type="lesson_plan", artifact_id=plan.id
    )


def _require_lesson_plan(db: Session, plan_id: str) -> SavedLessonPlan:
    plan = db.get(SavedLessonPlan, plan_id)
    if plan is None:
        raise AppException(code=40401, message="lesson plan not found", status_code=404)
    return plan
