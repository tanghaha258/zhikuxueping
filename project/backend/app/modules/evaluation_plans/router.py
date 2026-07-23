"""评价计划领域 API 路由（计划 Task 4）。

端点前缀：/api/v1/evaluation-plans

覆盖：
- 量规版本管理（创建/发布/归档）
- 量规维度 CRUD
- 证据 CRUD
- 评价计划快照 + 完整性校验
- 评价记录创建 + 状态机迁移
- 分维度评分（新增/更新/列表）
- 复核队列 + 教师确认
- 提交状态机迁移
- 旧版评价列表（兼容）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.evaluation_plans import service
from app.schemas.evaluation_plan import (
    EvaluationRecordCreate,
    EvaluationScoreCreate,
    EvaluationScoreUpdate,
    EvaluationTransitionRequest,
    EvidenceArtifactCreate,
    ReviewConfirmRequest,
    RubricCreate,
    RubricCriterionCreate,
    RubricCriterionUpdate,
    SubmissionTransitionRequest,
)

router = APIRouter(prefix="/evaluation-plans", tags=["评价计划"])


# ── 量规版本管理 ──────────────────────────────────────────────
@router.post("/rubrics", summary="新建量规版本")
def create_rubric_api(
    data: RubricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rubric = service.create_rubric(db, current_user, data.project_id, data)
    return success_response(
        {
            "id": rubric.id,
            "project_id": rubric.project_id,
            "version": rubric.version,
            "is_current": rubric.is_current,
            "status": rubric.status.value,
            "created_by": rubric.created_by,
        }
    )


@router.post("/rubrics/{rubric_id}/publish", summary="发布量规（含完整性校验）")
def publish_rubric_api(
    rubric_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = service.publish_rubric(db, current_user, rubric_id)
    return success_response(result)


@router.post("/rubrics/{rubric_id}/archive", summary="归档量规")
def archive_rubric_api(
    rubric_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rubric = service.archive_rubric(db, current_user, rubric_id)
    return success_response(
        {
            "id": rubric.id,
            "status": rubric.status.value,
        }
    )


# ── 量规维度 ──────────────────────────────────────────────────
@router.post("/criteria", summary="新增量规维度")
def add_criterion_api(
    data: RubricCriterionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    criterion = service.add_criterion(db, current_user, data)
    return success_response(_criterion_dict(criterion))


@router.put("/criteria/{criterion_id}", summary="更新量规维度")
def update_criterion_api(
    criterion_id: str,
    data: RubricCriterionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    criterion = service.update_criterion(db, current_user, criterion_id, data)
    return success_response(_criterion_dict(criterion))


@router.delete("/criteria/{criterion_id}", summary="删除量规维度")
def remove_criterion_api(
    criterion_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.remove_criterion(db, current_user, criterion_id)
    return success_response(None)


@router.get("/criteria", summary="列出量规维度")
def list_criteria_api(
    rubric_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_criteria(db, current_user, rubric_id)
    return success_response([_criterion_dict(c) for c in items])


# ── 证据 ──────────────────────────────────────────────────────
@router.post("/artifacts", summary="新增证据")
def add_artifact_api(
    data: EvidenceArtifactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    artifact = service.add_artifact(db, current_user, data)
    return success_response(_artifact_dict(artifact))


@router.get("/artifacts", summary="列出项目证据")
def list_artifacts_api(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_artifacts(db, current_user, project_id)
    return success_response([_artifact_dict(a) for a in items])


# ── 评价计划快照 + 完整性校验 ──────────────────────────────────
@router.get("/snapshot", summary="评价计划快照")
def get_snapshot_api(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    snapshot = service.get_plan_snapshot(db, current_user, project_id)
    return success_response(snapshot)


@router.get("/validate", summary="评价计划完整性校验")
def validate_plan_api(
    project_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = service.validate_evaluation_plan(db, current_user, project_id)
    return success_response(result)


# ── 评价记录 ──────────────────────────────────────────────────
@router.post("/records", summary="创建评价记录")
def create_record_api(
    data: EvaluationRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = service.create_record(db, current_user, data)
    return success_response(_record_dict(record))


@router.get("/records", summary="列出评价记录")
def list_records_api(
    project_id: str = Query(...),
    task_id: str = Query(None),
    student_id: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_records(
        db, current_user, project_id, task_id=task_id, student_id=student_id, status=status
    )
    return success_response([_record_dict(r) for r in items])


@router.get("/records/{record_id}", summary="评价记录详情")
def get_record_api(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = service.get_record(db, current_user, record_id)
    return success_response(_record_dict(record))


@router.post("/records/{record_id}/transition", summary="评价状态机迁移")
def transition_record_api(
    record_id: str,
    data: EvaluationTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = service.transition_record(db, current_user, record_id, data.target)
    return success_response(_record_dict(record))


# ── 分维度评分 ────────────────────────────────────────────────
@router.post("/scores", summary="新增分维度评分")
def add_score_api(
    data: EvaluationScoreCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = service.add_score(db, current_user, data)
    return success_response(_score_dict(score))


@router.put("/scores/{score_id}", summary="更新分维度评分")
def update_score_api(
    score_id: str,
    data: EvaluationScoreUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = service.update_score(db, current_user, score_id, data)
    return success_response(_score_dict(score))


@router.get("/scores", summary="列出分维度评分")
def list_scores_api(
    record_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_scores(db, current_user, record_id)
    return success_response([_score_dict(s) for s in items])


# ── 复核队列 + 教师确认 ────────────────────────────────────────
@router.get("/review-queue", summary="复核队列")
def get_review_queue_api(
    project_id: str = Query(...),
    task_id: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.get_review_queue(db, current_user, project_id, task_id=task_id)
    return success_response(items)


@router.post("/review-queue/{submission_id}/confirm", summary="教师确认复核")
def confirm_review_api(
    submission_id: str,
    data: ReviewConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = service.confirm_review(db, current_user, submission_id, data)
    return success_response(result)


# ── 提交状态机 ────────────────────────────────────────────────
@router.post("/submissions/{submission_id}/transition", summary="提交状态机迁移")
def transition_submission_api(
    submission_id: str,
    data: SubmissionTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = service.transition_submission(db, current_user, submission_id, data.target)
    return success_response(
        {
            "id": submission.id,
            "review_status": submission.review_status.value,
            "status": submission.status,
        }
    )


# ── 旧版评价 ──────────────────────────────────────────────────
@router.get("/legacy", summary="旧版简单评价列表")
def list_legacy_api(
    task_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_legacy_evaluations(db, current_user, task_id)
    return success_response(
        [
            {
                "id": e.id,
                "task_id": e.task_id,
                "student_id": e.student_id,
                "evaluator_id": e.evaluator_id,
                "score": e.score,
                "comment": e.comment,
                "eval_type": e.eval_type.value if hasattr(e.eval_type, "value") else str(e.eval_type),
                "is_legacy": True,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in items
        ]
    )


# ── 序列化辅助 ────────────────────────────────────────────────
def _criterion_dict(c) -> dict:
    return {
        "id": c.id,
        "rubric_id": c.rubric_id,
        "indicator_id": c.indicator_id,
        "dimension": c.dimension,
        "weight": c.weight,
        "ai_weight": c.ai_weight,
        "levels": c.levels or [],
    }


def _artifact_dict(a) -> dict:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "submission_id": a.submission_id,
        "indicator_id": a.indicator_id,
        "plan_id": a.plan_id,
        "source_type": a.source_type.value if hasattr(a.source_type, "value") else str(a.source_type),
        "content_ref": a.content_ref,
        "collected_by": a.collected_by,
        "collected_at": a.collected_at.isoformat() if a.collected_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _record_dict(record) -> dict:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "task_id": record.task_id,
        "student_id": record.student_id,
        "evaluator_id": record.evaluator_id,
        "subject_type": record.subject_type.value if hasattr(record.subject_type, "value") else str(record.subject_type),
        "subject_id": record.subject_id,
        "source": record.source.value if hasattr(record.source, "value") else str(record.source),
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "rubric_id": record.rubric_id,
        "total_score": record.total_score,
        "comment": record.comment,
        "confirmed_by": record.confirmed_by,
        "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
        "published_at": record.published_at.isoformat() if record.published_at else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _score_dict(s) -> dict:
    return {
        "id": s.id,
        "record_id": s.record_id,
        "criterion_id": s.criterion_id,
        "suggested_score": s.suggested_score,
        "final_score": s.final_score,
        "evidence_ref": s.evidence_ref,
        "ai_confidence": s.ai_confidence,
        "difference_reason": s.difference_reason,
    }
