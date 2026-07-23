"""批改反馈回流服务 — 批改结果更新题库质量数据"""
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.question import Question
from app.models.paper import Paper, PaperSubmission, AnswerKey
from app.models.learning_profile import QuestionUsageLog


def process_grading_feedback(db: Session, paper_id: str) -> dict:
    """处理试卷批改结果，更新题库"""
    paper = db.scalar(select(Paper).where(Paper.id == paper_id))
    if not paper:
        return {"error": "试卷不存在"}
    submissions = db.scalars(select(PaperSubmission).where(PaperSubmission.paper_id == paper_id)).all()
    if not submissions:
        return {"questions_updated": 0}
    answer_key = db.scalar(select(AnswerKey).where(AnswerKey.paper_id == paper_id))
    if not answer_key:
        return {"error": "未设置答案"}
    answers = answer_key.answers if isinstance(answer_key.answers, dict) else {}
    q_stats = {}
    for sub in submissions:
        answers_submitted = sub.answers_submitted if isinstance(sub.answers_submitted, dict) else {}
        for qid, correct_answer in answers.items():
            if qid not in q_stats:
                q_stats[qid] = {"total": 0, "correct": 0}
            q_stats[qid]["total"] += 1
            if answers_submitted.get(qid) == correct_answer:
                q_stats[qid]["correct"] += 1
    updated = 0
    for qid, stat in q_stats.items():
        rate = stat["correct"] / stat["total"] if stat["total"] > 0 else 0
        log = QuestionUsageLog(
            id=str(uuid.uuid4()), question_id=qid, paper_id=paper_id,
            usage_type="paper", class_id=getattr(paper, "class_id", None),
            total_count=stat["total"], correct_count=stat["correct"],
            correct_rate=round(rate, 2),
        )
        db.add(log)
        q = db.scalar(select(Question).where(Question.id == qid))
        if q:
            q.avg_correct_rate = round(rate, 2)
            q.usage_count = (q.usage_count or 0) + stat["total"]
            q.last_used_at = datetime.now()
            updated += 1
    db.flush()
    return {"questions_updated": updated, "total_submissions": len(submissions)}


def get_paper_grading_stats(db: Session, paper_id: str) -> dict:
    """获取试卷批改统计"""
    submissions = db.scalars(select(PaperSubmission).where(PaperSubmission.paper_id == paper_id)).all()
    total = len(submissions)
    graded = sum(1 for s in submissions if s.score is not None)
    return {"paper_id": paper_id, "total": total, "graded": graded, "pending": total - graded}
