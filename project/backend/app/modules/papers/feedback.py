import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_profile import QuestionUsageLog
from app.models.paper import AnswerKey, Paper, PaperSubmission
from app.models.question import Question


def process_grading_feedback(db: Session, paper_id: str) -> dict:
    paper = db.scalar(select(Paper).where(Paper.id == paper_id))
    if not paper:
        return {"error": "试卷不存在"}

    submissions = list(db.scalars(select(PaperSubmission).where(PaperSubmission.paper_id == paper_id)).all())
    if not submissions:
        return {"questions_updated": 0}

    answer_key = db.scalar(select(AnswerKey).where(AnswerKey.paper_id == paper_id))
    if not answer_key:
        return {"error": "未设置答案"}

    answers = answer_key.answers if isinstance(answer_key.answers, dict) else {}
    question_stats: dict[str, dict[str, int]] = {}
    for submission in submissions:
        submitted_answers = submission.answers_submitted if isinstance(submission.answers_submitted, dict) else {}
        for question_id, correct_answer in answers.items():
            stat = question_stats.setdefault(question_id, {"total": 0, "correct": 0})
            stat["total"] += 1
            if submitted_answers.get(question_id) == correct_answer:
                stat["correct"] += 1

    updated = 0
    for question_id, stat in question_stats.items():
        correct_rate = stat["correct"] / stat["total"] if stat["total"] else 0
        db.add(
            QuestionUsageLog(
                id=str(uuid.uuid4()),
                question_id=question_id,
                paper_id=paper_id,
                usage_type="paper",
                class_id=getattr(paper, "class_id", None),
                total_count=stat["total"],
                correct_count=stat["correct"],
                correct_rate=round(correct_rate, 2),
            )
        )
        question = db.scalar(select(Question).where(Question.id == question_id))
        if question:
            question.avg_correct_rate = round(correct_rate, 2)
            question.usage_count = (question.usage_count or 0) + stat["total"]
            question.last_used_at = datetime.now()
            updated += 1

    db.flush()
    return {"questions_updated": updated, "total_submissions": len(submissions)}


def get_paper_grading_stats(db: Session, paper_id: str) -> dict:
    submissions = list(db.scalars(select(PaperSubmission).where(PaperSubmission.paper_id == paper_id)).all())
    total = len(submissions)
    graded = sum(submission.score is not None for submission in submissions)
    return {"paper_id": paper_id, "total": total, "graded": graded, "pending": total - graded}
