"""项目学情诊断服务（Task 6）。

基于真实数据聚合班级画像、薄弱点与分层建议：
- 数据来源只包含项目班级、前测、提交、已发布评价与题目作答。
- 无证据时返回 ``insufficient_evidence`` 与空 segments，绝不为随机画像或伪成功。
- 掌握度与分层仅依据已发布评价分数计算，未发布评价不计入（学生不可见）。
- AI 失败时由教师人工诊断（teacher_note 留痕），不显示成功。
所有查询和操作复用项目读写授权策略，带学校作用域。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.project import Project
from app.models.project_learning_insight import ProjectLearningInsight
from app.modules.project_learning_insights import policy
from app.modules.project_learning_insights.repository import (
    ProjectLearningInsightRepository,
    utc_now,
)
from app.modules.projects.policy import (
    ensure_can_manage,
    ensure_can_read,
    ensure_not_archived,
)
from app.modules.projects.repository import ProjectRepository

# 分层阈值（掌握度 0-1）
_MASTERY_HIGH = 0.8
_MASTERY_MID = 0.6


# ============================================================
# generate
# ============================================================
def generate(db: Session, actor, project_id: str) -> dict:
    """POST /projects/{project_id}/insights/generate 服务实现。"""
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_manage(actor, project, class_ids)
    ensure_not_archived(project)

    repo = ProjectLearningInsightRepository(db)
    counts = repo.source_counts(project.id)
    now = utc_now()

    total_evidence = sum(counts.values())
    if total_evidence == 0:
        snapshot = None
        segments: list = []
        overall_mastery: Optional[float] = None
        weak_points: list = []
        teaching_suggestions: list = []
        status = "insufficient_evidence"
    else:
        snapshot, segments, overall_mastery, weak_points, teaching_suggestions = _compute_snapshot(
            repo, project.id
        )
        status = "draft"

    insight = ProjectLearningInsight(
        project_id=project.id,
        snapshot=snapshot,
        source_counts=counts,
        evidence_cutoff=now,
        status=status,
        generated_at=now,
        generated_by=actor.id,
        is_current=True,
    )
    repo.mark_previous_non_current(project.id)
    repo.create(insight)
    _commit(db)
    db.refresh(insight)
    return _to_dict(insight, segments, overall_mastery, weak_points, teaching_suggestions)


# ============================================================
# latest
# ============================================================
def get_latest(db: Session, actor, project_id: str) -> Optional[dict]:
    """GET /projects/{project_id}/insights/latest 服务实现。"""
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_read(actor, project, class_ids)

    insight = ProjectLearningInsightRepository(db).get_current(project.id)
    if insight is None:
        return None
    return _to_dict_from_model(insight)


# ============================================================
# confirm
# ============================================================
def confirm(db: Session, actor, project_id: str, insight_id: str, teacher_note: Optional[str]) -> dict:
    """POST /projects/{project_id}/insights/{insight_id}/confirm 服务实现。"""
    project = _require_project(db, project_id)
    class_ids = ProjectRepository(db).class_ids(project.id)
    ensure_can_manage(actor, project, class_ids)
    ensure_not_archived(project)

    repo = ProjectLearningInsightRepository(db)
    insight = repo.get_by_id(project.id, insight_id)
    if insight is None:
        raise AppException(code=40401, message="诊断记录不存在", status_code=404)
    if insight.status == "insufficient_evidence":
        raise AppException(
            code=40901,
            message="无证据诊断不可确认为正式结论，请先导入前测或发布任务",
            status_code=409,
        )
    if insight.status == "confirmed":
        raise AppException(code=40901, message="诊断已确认，无需重复确认", status_code=409)

    insight.status = "confirmed"
    insight.confirmed_by = actor.id
    insight.confirmed_at = utc_now()
    note = teacher_note.strip() if teacher_note and teacher_note.strip() else None
    insight.teacher_note = note
    _commit(db)
    db.refresh(insight)
    return _to_dict_from_model(insight)


# ============================================================
# 内部：快照计算（基于真实已发布评价）
# ============================================================
def _compute_snapshot(repo: ProjectLearningInsightRepository, project_id: str) -> tuple:
    """从真实已发布评价计算掌握度、分层、薄弱点与教学建议。"""
    evals = repo.list_published_evaluations(project_id)
    task_max = repo.task_max_scores(project_id)

    # 按学生聚合掌握度（多名学生各自平均）
    per_student: dict[str, list[float]] = {}
    for ev in evals:
        max_score = task_max.get(ev.task_id, 100) if ev.task_id else 100
        if not max_score or max_score <= 0:
            max_score = 100
        mastery = (ev.total_score or 0) / max_score
        mastery = max(0.0, min(1.0, mastery))
        per_student.setdefault(ev.student_id, []).append(mastery)

    student_masteries = [sum(v) / len(v) for v in per_student.values()]

    if not student_masteries:
        # 有其他证据（前测/作答）但无已发布评价：无法计算掌握度，返回空分层
        snapshot = {
            "overall_mastery": None,
            "segments": [],
            "weak_points": [],
            "teaching_suggestions": ["已采集前测与作答证据，发布评价后可生成掌握度与分层建议"],
        }
        return snapshot, [], None, [], snapshot["teaching_suggestions"]

    overall = sum(student_masteries) / len(student_masteries)

    high = [m for m in student_masteries if m >= _MASTERY_HIGH]
    mid = [m for m in student_masteries if _MASTERY_MID <= m < _MASTERY_HIGH]
    low = [m for m in student_masteries if m < _MASTERY_MID]

    segments = [
        {"name": "掌握", "student_count": len(high), "mastery_range": [_MASTERY_HIGH, 1.0]},
        {"name": "基本掌握", "student_count": len(mid), "mastery_range": [_MASTERY_MID, _MASTERY_HIGH]},
        {"name": "待提升", "student_count": len(low), "mastery_range": [0.0, _MASTERY_MID]},
    ]

    weak_points: list[dict] = []
    if low:
        weak_points.append(
            {
                "area": "基础掌握待巩固",
                "student_count": len(low),
                "avg_mastery": round(sum(low) / len(low), 3),
            }
        )

    suggestions: list[str] = []
    if low:
        suggestions.append(f"为 {len(low)} 名待提升学生设计基础巩固任务")
    if mid:
        suggestions.append(f"为 {len(mid)} 名基本掌握学生提供提升练习")
    if high:
        suggestions.append(f"为 {len(high)} 名掌握学生设计拓展迁移任务")

    snapshot = {
        "overall_mastery": round(overall, 3),
        "segments": segments,
        "weak_points": weak_points,
        "teaching_suggestions": suggestions,
    }
    return snapshot, segments, round(overall, 3), weak_points, suggestions


# ============================================================
# 内部：模型 → 响应字典
# ============================================================
def _to_dict_from_model(insight: ProjectLearningInsight) -> dict:
    snapshot = insight.snapshot or {}
    return _to_dict(
        insight,
        segments=snapshot.get("segments", []),
        overall_mastery=snapshot.get("overall_mastery"),
        weak_points=snapshot.get("weak_points", []),
        teaching_suggestions=snapshot.get("teaching_suggestions", []),
    )


def _to_dict(
    insight: ProjectLearningInsight,
    segments: list,
    overall_mastery: Optional[float],
    weak_points: list,
    teaching_suggestions: list,
) -> dict:
    counts = insight.source_counts or {
        "pre_test": 0,
        "submissions": 0,
        "evaluations": 0,
        "question_answers": 0,
    }
    return {
        "id": insight.id,
        "project_id": insight.project_id,
        "status": insight.status,
        "segments": segments,
        "overall_mastery": overall_mastery,
        "weak_points": weak_points,
        "teaching_suggestions": teaching_suggestions,
        "source_counts": counts,
        "evidence_cutoff": insight.evidence_cutoff,
        "generated_at": insight.generated_at,
        "generated_by": insight.generated_by,
        "confirmed_by": insight.confirmed_by,
        "confirmed_at": insight.confirmed_at,
        "teacher_note": insight.teacher_note,
        "is_current": insight.is_current,
    }


def _require_project(db: Session, project_id: str) -> Project:
    project = ProjectRepository(db).get(project_id)
    if not project:
        raise AppException(code=40401, message="项目不存在", status_code=404)
    return project


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
