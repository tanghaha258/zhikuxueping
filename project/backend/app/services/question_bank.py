import json
import re
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.modules.ai_gateway import complete
from app.models.ai_provider import AiProvider
from app.models.question import Question
from app.schemas.question_bank import AiGenerateRequest, QuestionCreate, QuestionUpdate


def list_questions(
    db: Session,
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
    q = select(Question)

    if visibility_filter is not None:
        q = q.where(visibility_filter)

    if subject:
        q = q.where(Question.subject == subject)
    if grade:
        q = q.where(Question.grade == grade)
    if question_type:
        q = q.where(Question.question_type == question_type)
    if difficulty_min > 0:
        q = q.where(Question.difficulty >= difficulty_min)
    if difficulty_max < 5:
        q = q.where(Question.difficulty <= difficulty_max)
    if knowledge_point:
        q = q.where(Question.knowledge_points.contains(knowledge_point))
    if keyword:
        q = q.where(Question.content.contains(keyword))
    if status:
        q = q.where(Question.status == status)
    if source:
        q = q.where(Question.source == source)

    count_q = select(func.count()).select_from(q.subquery())
    total = db.execute(count_q).scalar() or 0

    q = q.order_by(Question.created_at.desc()).offset(skip).limit(limit)
    items = list(db.execute(q).scalars().all())
    return items, total


def get_question(db: Session, question_id: str) -> Optional[Question]:
    return db.get(Question, question_id)


def create_question(db: Session, data: QuestionCreate, user_id: str) -> Question:
    obj = Question(
        subject=data.subject,
        grade=data.grade,
        question_type=data.question_type,
        difficulty=data.difficulty,
        content=data.content,
        options=data.options,
        answer=data.answer,
        analysis=data.analysis,
        score=data.score,
        knowledge_points=data.knowledge_points,
        source="manual",
        status="published",
        created_by=user_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_question(db: Session, question_id: str, data: QuestionUpdate) -> Optional[Question]:
    obj = db.get(Question, question_id)
    if not obj:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


def delete_question(db: Session, question_id: str) -> bool:
    obj = db.get(Question, question_id)
    if not obj:
        return False
    db.delete(obj)
    db.commit()
    return True


def batch_import_questions(
    db: Session, data_list: list[dict], user_id: str
) -> tuple[int, int, list[str]]:
    imported = 0
    failed = 0
    errors = []
    for i, item in enumerate(data_list):
        try:
            obj = Question(
                subject=item.get("subject", ""),
                grade=item.get("grade", ""),
                question_type=item.get("question_type", ""),
                difficulty=item.get("difficulty", 3),
                content=item.get("content", ""),
                options=item.get("options"),
                answer=item.get("answer"),
                analysis=item.get("analysis"),
                score=item.get("score", 5.0),
                knowledge_points=item.get("knowledge_points", "[]"),
                source="batch_import",
                status="published",
                created_by=user_id,
            )
            db.add(obj)
            db.flush()
            imported += 1
        except Exception as e:
            failed += 1
            errors.append(f"第 {i + 1} 行导入失败: {str(e)}")
    db.commit()
    return imported, failed, errors


def ai_generate_questions(
    db: Session, data: AiGenerateRequest, user_id: str
) -> list[Question]:
    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()
    if not provider:
        raise ValueError("没有可用的 AI Provider")

    kp_str = "、".join(data.knowledge_points) if data.knowledge_points else "通用"
    prompt = f"""你是一位初中{data.subject}教师，请为{data.grade}年级学生生成{data.count}道{data.question_type}，难度{data.difficulty}/5，知识点范围：{kp_str}。

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

确保输出是合法的 JSON，不要添加任何额外文字。"""

    content = complete(
        provider.api_url,
        provider.api_key,
        provider.model,
        [{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
        timeout=180.0,
    )

    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if not json_match:
        raise ValueError("AI 返回格式异常")

    parsed = json.loads(json_match.group())
    questions_data = parsed.get("questions", [])
    created = []

    for qd in questions_data:
        obj = Question(
            subject=data.subject,
            grade=data.grade,
            question_type=data.question_type,
            difficulty=qd.get("difficulty", data.difficulty),
            content=qd.get("content", ""),
            options=qd.get("options"),
            answer=qd.get("answer", ""),
            analysis=qd.get("analysis", ""),
            score=qd.get("score", 5.0),
            knowledge_points=json.dumps(data.knowledge_points, ensure_ascii=False),
            source="ai_generated",
            status="draft",
            created_by=user_id,
        )
        db.add(obj)
        created.append(obj)

    db.commit()
    for obj in created:
        db.refresh(obj)
    return created


# ──────────────────────────────────────────────
# 题目质量统计 & 详情
# ──────────────────────────────────────────────

def get_quality_stats(db: Session, subject: str = "", visibility_filter=None) -> dict:
    """题库质量统计概览"""
    q = select(func.count(Question.id)).where(Question.status != "archived")
    if visibility_filter is not None:
        q = q.where(visibility_filter)
    if subject:
        q = q.where(Question.subject == subject)
    total = db.scalar(q) or 0

    dist = {}
    for level in ["excellent", "good", "normal", "poor"]:
        lq = select(func.count(Question.id)).where(Question.quality_level == level)
        if visibility_filter is not None:
            lq = lq.where(visibility_filter)
        if subject:
            lq = lq.where(Question.subject == subject)
        dist[level] = db.scalar(lq) or 0

    dq = select(func.avg(Question.difficulty_calibrated)).where(Question.difficulty_calibrated.isnot(None))
    if visibility_filter is not None:
        dq = dq.where(visibility_filter)
    if subject:
        dq = dq.where(Question.subject == subject)
    avg_diff = db.scalar(dq) or 0

    dcq = select(func.avg(Question.discrimination)).where(Question.discrimination.isnot(None))
    if visibility_filter is not None:
        dcq = dcq.where(visibility_filter)
    if subject:
        dcq = dcq.where(Question.subject == subject)
    avg_disc = db.scalar(dcq) or 0

    return {
        "total_questions": total,
        "quality_distribution": dist,
        "avg_difficulty": round(float(avg_diff), 2),
        "avg_discrimination": round(float(avg_disc), 2),
        "knowledge_coverage": 0.85,
    }


def get_question_quality_detail(db: Session, question_id: str) -> dict | None:
    """获取单题质量详情"""
    q = db.get(Question, question_id)
    if not q:
        return None
    return {
        "quality_score": float(q.quality_score or 50),
        "quality_level": q.quality_level or "normal",
        "usage_count": q.usage_count or 0,
        "avg_correct_rate": float(q.avg_correct_rate) if q.avg_correct_rate else None,
        "difficulty_calibrated": float(q.difficulty_calibrated) if q.difficulty_calibrated else None,
        "discrimination": float(q.discrimination) if q.discrimination else None,
        "calibration_history": [],
    }


def update_question_quality(db: Session, question_id: str, data) -> dict | None:
    """更新题目质量参数（data 可为 dict 或 Pydantic model）"""
    q = db.get(Question, question_id)
    if not q:
        return None

    # 兼容 dict 和 Pydantic model
    if hasattr(data, "model_dump"):
        update_data = data.model_dump(exclude_unset=True)
    elif isinstance(data, dict):
        update_data = data
    else:
        update_data = {}

    for key in ["quality_score", "quality_level", "difficulty_calibrated", "discrimination"]:
        if key in update_data:
            setattr(q, key, update_data[key])

    db.flush()
    return {"updated": True}
