from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.saved_lesson_plan import SavedLessonPlan
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
