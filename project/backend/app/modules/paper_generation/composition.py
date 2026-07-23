import json
from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.question import Question


def parse_sections(sections_json: str) -> list[dict]:
    try:
        sections = json.loads(sections_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("sections must be a JSON array") from exc
    if not isinstance(sections, list):
        raise ValueError("sections must be a JSON array")
    return sections


def estimate_total_questions(sections_json: str | None) -> int:
    if not sections_json:
        return 10
    try:
        return sum(section.get("count", 0) for section in parse_sections(sections_json))
    except ValueError:
        return 10


def pick_from_bank(
    db,
    subject: str,
    grade: str,
    question_type: str,
    difficulty: str,
    knowledge_points: list[str] | None,
    count: int,
    visibility_filter=None,
) -> list[Question]:
    statement = select(Question).where(
        Question.subject == subject,
        Question.grade == grade,
        Question.question_type == question_type,
        Question.status == "published",
    )
    if visibility_filter is not None:
        statement = statement.where(visibility_filter)
    if difficulty == "easy":
        statement = statement.where(Question.difficulty <= 2)
    elif difficulty == "hard":
        statement = statement.where(Question.difficulty >= 4)
    else:
        statement = statement.where(Question.difficulty.between(2, 4))
    if knowledge_points:
        knowledge_points_json = json.dumps(knowledge_points, ensure_ascii=False)
        statement = statement.where(Question.knowledge_points.contains(knowledge_points_json[1:-1]))
    return list(db.execute(statement.order_by(func.random()).limit(count)).scalars().all())


def question_to_paper_question(question: Question, question_type: str, score: float) -> dict:
    options = None
    if question.options:
        try:
            options = json.loads(question.options)
        except json.JSONDecodeError:
            options = None
    return {
        "index": 0,
        "type": question_type,
        "score": score,
        "content": question.content,
        "options": options,
        "answer": question.answer or "",
        "analysis": question.analysis or "",
        "_from_bank": True,
        "_question_id": question.id,
    }


def compose_questions(
    sections: Sequence[dict],
    *,
    bank_ratio: float,
    bank_questions_by_section: Sequence[Sequence[dict]],
    ai_questions: Sequence[dict],
) -> list[dict]:
    final_questions: list[dict] = []
    used_ai_indexes: set[int] = set()

    def add_question(question: dict) -> None:
        copied = dict(question)
        copied["index"] = len(final_questions) + 1
        final_questions.append(copied)

    def add_ai_questions(question_type: str, count: int) -> int:
        added = 0
        for ai_index, question in enumerate(ai_questions):
            if added >= count:
                break
            if ai_index in used_ai_indexes or question.get("type") != question_type:
                continue
            add_question(question)
            used_ai_indexes.add(ai_index)
            added += 1
        return added

    def add_any_ai_questions(count: int) -> None:
        added = 0
        for ai_index, question in enumerate(ai_questions):
            if added >= count:
                break
            if ai_index in used_ai_indexes:
                continue
            add_question(question)
            used_ai_indexes.add(ai_index)
            added += 1

    for section_index, section in enumerate(sections):
        question_type = section.get("type", "choice")
        section_count = section.get("count", 0)
        bank_count = max(0, int(section_count * bank_ratio))
        bank_questions = bank_questions_by_section[section_index] if section_index < len(bank_questions_by_section) else []

        for question in bank_questions[:bank_count]:
            add_question(question)

        ai_needed = section_count - bank_count
        matching_ai_count = add_ai_questions(question_type, ai_needed)
        if matching_ai_count < ai_needed:
            add_any_ai_questions(ai_needed - matching_ai_count)

    return final_questions
