import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning_profile import ClassLearningReport
from app.models.submission import Submission
from app.models.user import User


def generate_class_learning_profile(db: Session, class_id: str, subject: str) -> dict:
    students = db.scalars(
        select(User).where(User.class_id == class_id, User.role == "student")
    ).all()
    if not students:
        return {
            "class_id": class_id,
            "subject": subject,
            "overall_mastery": 0,
            "knowledge_mastery": {},
            "weak_points": [],
            "strong_points": [],
            "student_count": 0,
        }

    total_score = 0
    total_count = 0
    for student in students:
        submissions = db.scalars(
            select(Submission).where(
                Submission.student_id == student.id,
                Submission.status.in_(["submitted", "reviewed"]),
            )
        ).all()
        for submission in submissions:
            if submission.score is not None:
                total_score += float(submission.score)
                total_count += 1

    knowledge_mastery: dict = {}
    weak_points = [
        knowledge_point
        for knowledge_point, mastery in knowledge_mastery.items()
        if mastery < 0.6
    ]
    strong_points = [
        knowledge_point
        for knowledge_point, mastery in knowledge_mastery.items()
        if mastery >= 0.8
    ]
    return {
        "class_id": class_id,
        "subject": subject,
        "overall_mastery": round(total_score / total_count * 100, 1)
        if total_count
        else 0,
        "knowledge_mastery": knowledge_mastery,
        "weak_points": weak_points,
        "strong_points": strong_points,
        "student_count": len(students),
    }


def generate_class_report(db: Session, class_id: str, subject: str) -> dict:
    profile = generate_class_learning_profile(db, class_id, subject)
    recommendations = [
        {
            "type": "reinforce",
            "knowledge_point": knowledge_point,
            "suggestion": f"\u5efa\u8bae\u52a0\u5f3a\u300a{knowledge_point}\u300b\u76f8\u5173\u7ec3\u4e60",
        }
        for knowledge_point in profile["weak_points"]
    ]
    if len(profile["weak_points"]) > 3:
        recommendations.append(
            {
                "type": "strategy",
                "suggestion": "\u8584\u5f31\u77e5\u8bc6\u70b9\u8f83\u591a\uff0c"
                "\u5efa\u8bae\u91c7\u7528\u5206\u5c42\u6559\u5b66",
            }
        )

    report = ClassLearningReport(
        class_id=class_id,
        subject=subject,
        report_type="weekly",
        report_date=date.today(),
        overall_mastery=profile["overall_mastery"],
        knowledge_mastery=json.dumps(profile["knowledge_mastery"], ensure_ascii=False),
        weak_points=json.dumps(profile["weak_points"], ensure_ascii=False),
        strong_points=json.dumps(profile["strong_points"], ensure_ascii=False),
        recommendations=json.dumps(recommendations, ensure_ascii=False),
        student_count=profile["student_count"],
    )
    db.add(report)
    try:
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        raise
    return {"id": report.id, **profile, "recommendations": recommendations}


def get_class_reports(
    db: Session,
    class_id: str,
    subject: str,
    limit: int = 10,
) -> list:
    reports = db.scalars(
        select(ClassLearningReport)
        .where(
            ClassLearningReport.class_id == class_id,
            ClassLearningReport.subject == subject,
        )
        .order_by(ClassLearningReport.report_date.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": report.id,
            "report_type": report.report_type,
            "report_date": str(report.report_date),
            "overall_mastery": float(report.overall_mastery or 0),
            "student_count": report.student_count,
        }
        for report in reports
    ]
