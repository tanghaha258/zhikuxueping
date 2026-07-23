from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_provider import AiProvider
from app.models.question import Question


class QuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_filtered(
        self,
        *,
        subject: str = "",
        grade: str = "",
        question_type: str = "",
        difficulty_min: int = 0,
        difficulty_max: int = 5,
        knowledge_point: str = "",
        keyword: str = "",
        status: str = "",
        source: str = "",
        skip: int = 0,
        limit: int = 20,
        visibility_filter=None,
    ) -> tuple[list[Question], int]:
        statement = select(Question)
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        if subject:
            statement = statement.where(Question.subject == subject)
        if grade:
            statement = statement.where(Question.grade == grade)
        if question_type:
            statement = statement.where(Question.question_type == question_type)
        if difficulty_min > 0:
            statement = statement.where(Question.difficulty >= difficulty_min)
        if difficulty_max < 5:
            statement = statement.where(Question.difficulty <= difficulty_max)
        if knowledge_point:
            statement = statement.where(Question.knowledge_points.contains(knowledge_point))
        if keyword:
            statement = statement.where(Question.content.contains(keyword))
        if status:
            statement = statement.where(Question.status == status)
        if source:
            statement = statement.where(Question.source == source)
        total = self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = list(self.db.scalars(statement.order_by(Question.created_at.desc()).offset(skip).limit(limit)).all())
        return items, total

    def get(self, question_id: str) -> Question | None:
        return self.db.get(Question, question_id)

    def get_active_provider(self) -> AiProvider | None:
        return self.db.scalar(select(AiProvider).where(AiProvider.status == "active"))

    def add(self, question: Question) -> None:
        self.db.add(question)

    def delete(self, question: Question) -> None:
        self.db.delete(question)

    def quality_stats(self, subject: str, visibility_filter) -> dict:
        def scoped(column, *, exclude_archived: bool = False):
            statement = select(column)
            if exclude_archived:
                statement = statement.where(Question.status != "archived")
            if visibility_filter is not None:
                statement = statement.where(visibility_filter)
            if subject:
                statement = statement.where(Question.subject == subject)
            return statement

        distribution = {
            level: self.db.scalar(scoped(func.count(Question.id)).where(Question.quality_level == level)) or 0
            for level in ("excellent", "good", "normal", "poor")
        }
        return {
            "total_questions": self.db.scalar(scoped(func.count(Question.id), exclude_archived=True)) or 0,
            "quality_distribution": distribution,
            "avg_difficulty": round(float(self.db.scalar(scoped(func.avg(Question.difficulty_calibrated))) or 0), 2),
            "avg_discrimination": round(float(self.db.scalar(scoped(func.avg(Question.discrimination))) or 0), 2),
            "knowledge_coverage": 0.85,
        }
