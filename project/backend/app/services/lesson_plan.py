from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.saved_lesson_plan import SavedLessonPlan
from app.schemas.lesson_plan import LessonPlanCreate, LessonPlanUpdate


def list_plans(db: Session, user_id: str) -> list[SavedLessonPlan]:
    stmt = select(SavedLessonPlan).where(
        SavedLessonPlan.user_id == user_id
    ).order_by(SavedLessonPlan.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def create_plan(db: Session, data: LessonPlanCreate, user_id: str) -> SavedLessonPlan:
    plan = SavedLessonPlan(
        user_id=user_id,
        title=data.title,
        content=data.content,
        subject=data.subject,
        grade=data.grade,
        topic=data.topic,
        duration=data.duration,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_plan(db: Session, plan_id: str) -> SavedLessonPlan | None:
    return db.get(SavedLessonPlan, plan_id)


def update_plan(db: Session, plan_id: str, data: LessonPlanUpdate) -> SavedLessonPlan | None:
    plan = db.get(SavedLessonPlan, plan_id)
    if not plan:
        return None
    if data.title is not None:
        plan.title = data.title
    if data.content is not None:
        plan.content = data.content
    db.commit()
    db.refresh(plan)
    return plan


def delete_plan(db: Session, plan_id: str) -> bool:
    plan = db.get(SavedLessonPlan, plan_id)
    if not plan:
        return False
    db.delete(plan)
    db.commit()
    return True
