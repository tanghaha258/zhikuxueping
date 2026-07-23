import json
import re

from sqlalchemy.orm import Session

from app.models.question import Question
from app.modules.ai_gateway import complete
from app.modules.question_bank.repository import QuestionRepository
from app.schemas.question_bank import AiGenerateRequest, QuestionCreate, QuestionUpdate


def list_questions(db: Session, **filters) -> tuple[list[Question], int]:
    return QuestionRepository(db).list_filtered(**filters)


def get_question(db: Session, question_id: str) -> Question | None:
    return QuestionRepository(db).get(question_id)


def create_question(db: Session, data: QuestionCreate, user_id: str) -> Question:
    question = _new_question(data.model_dump(), user_id, source="manual", status="published")
    QuestionRepository(db).add(question)
    return _commit_and_refresh(db, question)


def update_question(db: Session, question_id: str, data: QuestionUpdate) -> Question | None:
    question = get_question(db, question_id)
    if not question:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    return _commit_and_refresh(db, question)


def delete_question(db: Session, question_id: str) -> bool:
    repository = QuestionRepository(db)
    question = repository.get(question_id)
    if not question:
        return False
    repository.delete(question)
    _commit(db)
    return True


def batch_import_questions(db: Session, data_list: list[dict], user_id: str) -> tuple[int, int, list[str]]:
    repository = QuestionRepository(db)
    imported, failed, errors = 0, 0, []
    for index, item in enumerate(data_list):
        try:
            with db.begin_nested():
                repository.add(_new_question(item, user_id, source="batch_import", status="published"))
                db.flush()
            imported += 1
        except Exception as error:
            failed += 1
            errors.append(f"Row {index + 1}: {error}")
    _commit(db)
    return imported, failed, errors


def ai_generate_questions(db: Session, data: AiGenerateRequest, user_id: str) -> list[Question]:
    provider = QuestionRepository(db).get_active_provider()
    if not provider:
        raise ValueError("No active AI provider")
    prompt = build_generation_prompt(data)
    content = complete(
        provider.api_url, provider.api_key, provider.model, [{"role": "user", "content": prompt}],
        temperature=0.7, max_tokens=4096, timeout=180.0,
    )
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("Invalid AI response format")
    question_data = json.loads(match.group()).get("questions", [])
    repository = QuestionRepository(db)
    questions = []
    for item in question_data:
        question = Question(
            subject=data.subject, grade=data.grade, question_type=data.question_type,
            difficulty=item.get("difficulty", data.difficulty), content=item.get("content", ""),
            options=item.get("options"), answer=item.get("answer", ""), analysis=item.get("analysis", ""),
            score=item.get("score", 5.0), knowledge_points=json.dumps(data.knowledge_points, ensure_ascii=False),
            source="ai_generated", status="draft", created_by=user_id,
        )
        repository.add(question)
        questions.append(question)
    _commit(db)
    for question in questions:
        db.refresh(question)
    return questions


def get_quality_stats(db: Session, subject: str = "", visibility_filter=None) -> dict:
    return QuestionRepository(db).quality_stats(subject, visibility_filter)


def get_question_quality_detail(db: Session, question_id: str) -> dict | None:
    question = get_question(db, question_id)
    if not question:
        return None
    return {
        "quality_score": float(question.quality_score or 50),
        "quality_level": question.quality_level or "normal",
        "usage_count": question.usage_count or 0,
        "avg_correct_rate": float(question.avg_correct_rate) if question.avg_correct_rate else None,
        "difficulty_calibrated": float(question.difficulty_calibrated) if question.difficulty_calibrated else None,
        "discrimination": float(question.discrimination) if question.discrimination else None,
        "calibration_history": [],
    }


def update_question_quality(db: Session, question_id: str, data) -> dict | None:
    question = get_question(db, question_id)
    if not question:
        return None
    values = data.model_dump(exclude_unset=True) if hasattr(data, "model_dump") else data if isinstance(data, dict) else {}
    for field in ("quality_score", "quality_level", "difficulty_calibrated", "discrimination"):
        if field in values:
            setattr(question, field, values[field])
    db.flush()
    return {"updated": True}


def build_generation_prompt(data: AiGenerateRequest) -> str:
    knowledge_points = "、".join(data.knowledge_points) if data.knowledge_points else "通用"
    return f'''你是一位初中{data.subject}教师，请为{data.grade}学生生成{data.count}道{data.question_type}，难度{data.difficulty}/5，知识点范围：{knowledge_points}。
每道题请严格按以下 JSON 格式输出，不要包含其他内容：
{{
  "questions": [
    {{
      "content": "题目内容（可用HTML标签）",
      "options": "[{{\\"label\\":\\"A\\",\\"content\\":\\"选项内容\\"}},...]" | null,
      "answer": "参考答案",
      "analysis": "解析（可用HTML）",
      "difficulty": 3,
      "score": 5
    }}
  ]
}}
确保输出是合法的 JSON，不要添加任何额外文字。'''


def _new_question(values: dict, user_id: str, *, source: str, status: str) -> Question:
    return Question(
        subject=values.get("subject", ""), grade=values.get("grade", ""),
        question_type=values.get("question_type", ""), difficulty=values.get("difficulty", 3),
        content=values.get("content", ""), options=values.get("options"), answer=values.get("answer"),
        analysis=values.get("analysis"), score=values.get("score", 5.0),
        knowledge_points=values.get("knowledge_points", "[]"), source=source, status=status, created_by=user_id,
    )


def _commit_and_refresh(db: Session, record: Question) -> Question:
    _commit(db)
    db.refresh(record)
    return record


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
