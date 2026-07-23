"""AI 批改评价统一来源测试（计划 Task 2）。

验收要点：
- AI 成功时只创建 `EvaluationRecord`（status=DRAFT, source=ai），不写入旧 `Evaluation`。
- 返回 `evaluation_record_id`、`status`、`source`，不返回旧的 `evaluation_id`。
- AI 草稿对学生不可见（学生在反馈视图看不到未发布记录）。
- AI 失败时不写入分数，仅返回可审计的不可用结果。
- 旧 `Evaluation` 历史数据保留只读，不被新流程写入。
"""
import httpx

from app.models.ai_provider import AiProvider
from app.models.evaluation import Evaluation
from app.models.evaluation_plan import EvaluationRecord
from app.models.enums import EvaluationSource, EvaluationStatus
from app.models.submission import Submission
from app.models.task import Task
from app.modules.evaluations.ai_grading import evaluate_submission


def _submission_context(db_session, suffix: str) -> Submission:
    task = Task(
        id=f"ai-grading-task-{suffix}",
        project_id=f"ai-grading-project-{suffix}",
        title="AI grading task",
        created_by="ai-grading-teacher",
        max_score=100,
    )
    submission = Submission(
        id=f"ai-grading-submission-{suffix}",
        task_id=task.id,
        student_id="ai-grading-student",
        content="Student submission",
        status="submitted",
    )
    db_session.add_all([task, submission])
    db_session.flush()
    return submission


def test_submission_grading_returns_unavailable_without_an_active_provider(db_session):
    submission = _submission_context(db_session, "mock")

    result = evaluate_submission(db_session, submission.id, "ai-grading-teacher")

    # 无可用 Provider 时返回明确的不可用状态，且不写入 AI 分数或评价记录。
    assert result["status"] == "unavailable"
    assert result["error_code"] == "provider_unavailable"
    assert result.get("evaluation_record_id") is None
    assert "total_score" not in result
    assert "dimensions" not in result
    # 不创建任何评价记录（新旧都不写）
    assert db_session.query(Evaluation).filter_by(
        task_id=submission.task_id, student_id=submission.student_id
    ).count() == 0
    assert db_session.query(EvaluationRecord).filter_by(
        task_id=submission.task_id, student_id=submission.student_id
    ).count() == 0


def test_ai_draft_creates_evaluation_record_not_legacy_evaluation(db_session, monkeypatch):
    """AI 成功时创建 EvaluationRecord（DRAFT, source=ai），不写入旧 Evaluation。"""
    submission = _submission_context(db_session, "persisted")
    db_session.add(AiProvider(
        id="ai-grading-provider",
        name="AI grading provider",
        api_url="https://provider.example/v1",
        model="grading-model",
        api_key="grading-key",
        status="active",
    ))
    db_session.flush()
    monkeypatch.setattr(
        "app.modules.evaluations.ai_grading._call_evaluate_ai",
        lambda provider, prompt: {
            "dimensions": [{"name": "content", "score": 88, "comment": "good"}],
            "total_score": 88,
            "overall_comment": "Strong work",
        },
    )

    result = evaluate_submission(db_session, submission.id, "ai-grading-teacher")

    # 返回新契约：evaluation_record_id / status / source
    assert result["status"] == "draft"
    assert result["source"] == "ai"
    assert result["evaluation_record_id"] is not None
    assert "evaluation_id" not in result  # 不再返回旧字段
    assert result["total_score"] == 88
    assert result["overall_comment"] == "Strong work"

    # EvaluationRecord 已创建，状态为 DRAFT，来源为 AI
    record = db_session.query(EvaluationRecord).filter_by(
        task_id=submission.task_id, student_id=submission.student_id
    ).one()
    assert record.status == EvaluationStatus.DRAFT
    assert record.source == EvaluationSource.AI
    assert record.evaluator_id == "ai-grading-teacher"
    assert record.project_id == f"ai-grading-project-persisted"

    # 旧 Evaluation 表不写入新数据
    assert db_session.query(Evaluation).filter_by(
        task_id=submission.task_id, student_id=submission.student_id
    ).count() == 0


def _provider_context(db_session, suffix: str) -> Submission:
    submission = _submission_context(db_session, suffix)
    db_session.add(AiProvider(
        id=f"ai-grading-provider-{suffix}",
        name=f"AI grading provider {suffix}",
        api_url="https://provider.example/v1",
        model="grading-model",
        api_key="grading-key",
        status="active",
    ))
    db_session.flush()
    return submission


def test_submission_grading_returns_timeout_when_ai_call_times_out(db_session, monkeypatch):
    submission = _provider_context(db_session, "timeout")

    def _raise(provider, prompt):
        raise httpx.TimeoutException("timeout")
    monkeypatch.setattr("app.modules.evaluations.ai_grading._call_evaluate_ai", _raise)

    result = evaluate_submission(db_session, submission.id, "ai-grading-teacher")

    assert result["status"] == "unavailable"
    assert result["error_code"] == "timeout"
    assert result.get("evaluation_record_id") is None
    # 失败不写入任何评价记录
    assert db_session.query(EvaluationRecord).filter_by(task_id=submission.task_id).count() == 0
    assert db_session.query(Evaluation).filter_by(task_id=submission.task_id).count() == 0


def test_submission_grading_returns_invalid_output_when_ai_returns_no_json(db_session, monkeypatch):
    submission = _provider_context(db_session, "invalid")

    monkeypatch.setattr(
        "app.modules.evaluations.ai_grading._call_evaluate_ai",
        lambda provider, prompt: None,
    )

    result = evaluate_submission(db_session, submission.id, "ai-grading-teacher")

    assert result["status"] == "unavailable"
    assert result["error_code"] == "invalid_output"
    assert result.get("evaluation_record_id") is None
    assert db_session.query(EvaluationRecord).filter_by(task_id=submission.task_id).count() == 0
