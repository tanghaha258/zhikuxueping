"""题库质量引擎 — 难度校准、区分度、质量评分"""
import json
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.question import Question
from app.models.learning_profile import QuestionUsageLog, DifficultyCalibrationHistory


def calibrate_difficulty(db: Session, question_id: str) -> float:
    """基于 usage_logs 正确率校准难度（简化贝叶斯）"""
    q = db.scalar(select(Question).where(Question.id == question_id))
    if not q:
        return 0.5
    logs = db.scalars(select(QuestionUsageLog).where(QuestionUsageLog.question_id == question_id)).all()
    if not logs:
        return q.difficulty / 5.0
    total = sum(l.total_count for l in logs)
    correct = sum(l.correct_count for l in logs)
    if total == 0:
        return q.difficulty / 5.0
    raw_rate = correct / total
    prior_difficulty = q.difficulty / 5.0
    prior_weight = 3
    calibrated = (prior_difficulty * prior_weight + raw_rate * total) / (prior_weight + total)
    calibrated = max(0.05, min(0.95, calibrated))
    old_diff = q.difficulty_calibrated or prior_difficulty
    db.add(DifficultyCalibrationHistory(
        id=str(uuid.uuid4()), question_id=question_id,
        old_difficulty=float(old_diff), new_difficulty=float(calibrated),
        sample_size=total, old_correct_rate=float(raw_rate),
        calibration_method="bayesian"
    ))
    q.difficulty_calibrated = round(calibrated, 2)
    return calibrated


def calculate_discrimination(db: Session, question_id: str) -> float:
    """区分度 = 高分组正确率 - 低分组正确率"""
    logs = db.scalars(select(QuestionUsageLog).where(QuestionUsageLog.question_id == question_id)).all()
    if not logs:
        return 0.0
    rates = [float(l.correct_rate or 0) for l in logs if l.total_count and l.total_count > 0]
    if len(rates) < 2:
        return 0.0
    rates.sort(reverse=True)
    mid = len(rates) // 2
    high = sum(rates[:mid]) / max(mid, 1)
    low = sum(rates[mid:]) / max(len(rates) - mid, 1)
    disc = max(0.0, min(1.0, high - low))
    q = db.scalar(select(Question).where(Question.id == question_id))
    if q:
        q.discrimination = round(disc, 2)
    return disc


def calculate_quality_score(db: Session, question_id: str) -> float:
    """质量分 = 难度适中(40%) + 区分度(40%) + 使用频率(20%)"""
    q = db.scalar(select(Question).where(Question.id == question_id))
    if not q:
        return 50.0
    diff = q.difficulty_calibrated if q.difficulty_calibrated is not None else 0.5
    difficulty_score = max(0, 1.0 - abs(float(diff) - 0.5) * 2)
    disc = float(q.discrimination or 0)
    discrimination_score = min(disc / 0.4, 1.0)
    usage_score = min((q.usage_count or 0) / 100, 1.0)
    score = (difficulty_score * 0.4 + discrimination_score * 0.4 + usage_score * 0.2) * 100
    if score >= 80:
        q.quality_level = "excellent"
    elif score >= 60:
        q.quality_level = "good"
    elif score >= 40:
        q.quality_level = "normal"
    else:
        q.quality_level = "poor"
    q.quality_score = round(score, 2)
    return score


def update_question_stats(db: Session, question_id: str) -> dict:
    """聚合更新题目所有统计数据"""
    q = db.scalar(select(Question).where(Question.id == question_id))
    if not q:
        return {}
    logs = db.scalars(select(QuestionUsageLog).where(QuestionUsageLog.question_id == question_id)).all()
    total = sum(l.total_count for l in logs)
    correct = sum(l.correct_count for l in logs)
    q.avg_correct_rate = round(correct / total, 2) if total > 0 else None
    calibrate_difficulty(db, question_id)
    calculate_discrimination(db, question_id)
    calculate_quality_score(db, question_id)
    q.last_used_at = datetime.now()
    db.flush()
    return {"quality_score": float(q.quality_score or 0), "quality_level": q.quality_level}


def get_quality_stats(db: Session) -> dict:
    """全库质量统计"""
    total = db.scalar(select(func.count(Question.id)).where(Question.status != "archived")) or 0
    dist = {}
    for level in ["excellent", "good", "normal", "poor"]:
        dist[level] = db.scalar(select(func.count(Question.id)).where(Question.quality_level == level)) or 0
    avg_diff = db.scalar(select(func.avg(Question.difficulty_calibrated)).where(Question.difficulty_calibrated.isnot(None))) or 0
    avg_disc = db.scalar(select(func.avg(Question.discrimination)).where(Question.discrimination.isnot(None))) or 0
    kp_count = db.scalar(select(func.count(func.distinct(Question.knowledge_points)))) or 0
    return {
        "total_questions": total,
        "quality_distribution": dist,
        "avg_difficulty": round(float(avg_diff), 2),
        "avg_discrimination": round(float(avg_disc), 2),
        "knowledge_coverage": round(min(kp_count / 50, 1.0), 2),
    }


def get_question_quality_detail(db: Session, question_id: str) -> dict | None:
    """单题质量详情"""
    q = db.scalar(select(Question).where(Question.id == question_id))
    if not q:
        return None
    history = db.scalars(
        select(DifficultyCalibrationHistory)
        .where(DifficultyCalibrationHistory.question_id == question_id)
        .order_by(DifficultyCalibrationHistory.created_at.desc())
        .limit(10)
    ).all()
    return {
        "quality_score": float(q.quality_score or 50),
        "quality_level": q.quality_level or "normal",
        "usage_count": q.usage_count or 0,
        "avg_correct_rate": float(q.avg_correct_rate) if q.avg_correct_rate else None,
        "difficulty_calibrated": float(q.difficulty_calibrated) if q.difficulty_calibrated else None,
        "discrimination": float(q.discrimination) if q.discrimination else None,
        "calibration_history": [{"old": float(h.old_difficulty or 0), "new": float(h.new_difficulty or 0), "sample": h.sample_size, "method": h.calibration_method} for h in history],
    }
