"""学情分析服务 — 班级/学生学情画像、报告生成"""
import json
import uuid
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.question import Question
from app.models.paper import PaperSubmission, AnswerKey
from app.models.submission import Submission
from app.models.school import Class
from app.models.user import User
from app.models.learning_profile import ClassLearningReport


def generate_class_learning_profile(db: Session, class_id: str, subject: str) -> dict:
    """生成班级学情画像"""
    students = db.scalars(select(User).where(User.class_id == class_id, User.role == "student")).all()
    if not students:
        return {"class_id": class_id, "subject": subject, "overall_mastery": 0, "knowledge_mastery": {}, "weak_points": [], "strong_points": [], "student_count": 0}
    total_correct = 0
    total_count = 0
    for stu in students:
        subs = db.scalars(select(Submission).where(Submission.student_id == stu.id, Submission.status.in_(["submitted", "reviewed"]))).all()
        for sub in subs:
            if sub.score is not None:
                total_correct += float(sub.score)
                total_count += 1
    overall = round(total_correct / total_count * 100, 1) if total_count > 0 else 0
    kp_stats: dict = {}
    weak = [kp for kp, m in kp_stats.items() if m < 0.6]
    strong = [kp for kp, m in kp_stats.items() if m >= 0.8]
    return {"class_id": class_id, "subject": subject, "overall_mastery": overall, "knowledge_mastery": kp_stats, "weak_points": weak, "strong_points": strong, "student_count": len(students)}


def generate_class_report(db: Session, class_id: str, subject: str, report_type: str = "weekly") -> dict:
    """生成并保存班级学情报告"""
    profile = generate_class_learning_profile(db, class_id, subject)
    recommendations = []
    for kp in profile.get("weak_points", []):
        recommendations.append({"type": "reinforce", "knowledge_point": kp, "suggestion": f"建议加强「{kp}」相关练习"})
    if len(profile.get("weak_points", [])) > 3:
        recommendations.append({"type": "strategy", "suggestion": "薄弱知识点较多，建议采用分层教学"})
    report = ClassLearningReport(
        id=str(uuid.uuid4()), class_id=class_id, subject=subject,
        report_type=report_type, report_date=date.today(),
        overall_mastery=profile["overall_mastery"],
        knowledge_mastery=json.dumps(profile["knowledge_mastery"], ensure_ascii=False),
        weak_points=json.dumps(profile["weak_points"], ensure_ascii=False),
        strong_points=json.dumps(profile["strong_points"], ensure_ascii=False),
        recommendations=json.dumps(recommendations, ensure_ascii=False),
        student_count=profile["student_count"],
    )
    db.add(report)
    db.flush()
    return {"id": report.id, **profile, "recommendations": recommendations}


def get_class_reports(db: Session, class_id: str, subject: str, limit: int = 10) -> list:
    """查询班级历史报告"""
    rows = db.scalars(
        select(ClassLearningReport)
        .where(ClassLearningReport.class_id == class_id, ClassLearningReport.subject == subject)
        .order_by(ClassLearningReport.report_date.desc())
        .limit(limit)
    ).all()
    return [{"id": r.id, "report_type": r.report_type, "report_date": str(r.report_date), "overall_mastery": float(r.overall_mastery or 0), "student_count": r.student_count} for r in rows]
