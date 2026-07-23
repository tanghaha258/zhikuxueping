import httpx

from app.models.ai_provider import AiProvider
from app.models.paper import AnswerKey, PaperSubmission, SubmissionStatus
from app.modules.papers.ai_grading import evaluate_paper_submission


def _grading_context(db_session, suffix: str) -> tuple[PaperSubmission, AnswerKey]:
    paper_id = f"paper-ai-grading-{suffix}"
    submission = PaperSubmission(
        id=f"paper-ai-submission-{suffix}",
        paper_id=paper_id,
        student_id="paper-ai-student",
        content="Student answer",
    )
    answer_key = AnswerKey(
        id=f"paper-ai-answer-key-{suffix}",
        paper_id=paper_id,
        questions=[
            {
                "index": 0,
                "score": 10,
                "content": "Question content",
                "answer": "Reference answer",
                "student_answer": "Student answer",
            }
        ],
        total_score=10,
    )
    db_session.add_all([submission, answer_key])
    db_session.flush()
    return submission, answer_key


def test_paper_grading_returns_unavailable_without_an_active_provider(db_session):
    submission, answer_key = _grading_context(db_session, "fallback")

    result = evaluate_paper_submission(db_session, submission, answer_key)

    # 无可用 Provider 时不写入 AI 分数、不标记已批改。
    assert result["status"] == "unavailable"
    assert result["error_code"] == "provider_unavailable"
    assert submission.status == SubmissionStatus.PENDING
    assert submission.ai_score is None
    assert "total_score" not in result


def test_paper_grading_persists_successful_ai_result(db_session, monkeypatch):
    submission, answer_key = _grading_context(db_session, "provider")
    db_session.add(
        AiProvider(
            id="paper-ai-grading-provider",
            name="Paper AI grading provider",
            api_url="https://provider.example/v1",
            model="grading-model",
            api_key="grading-key",
            status="active",
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        "app.modules.papers.ai_grading._call_evaluate_ai",
        lambda provider, prompt: {
            "questions": [{"index": 1, "score": 8, "comment": "Good work"}],
            "overall_comment": "Strong work",
        },
    )

    result = evaluate_paper_submission(db_session, submission, answer_key)

    assert result["status"] == "succeeded"
    assert submission.status == SubmissionStatus.GRADED
    assert submission.ai_score == 8
    assert submission.ai_comment == "Strong work"
    assert result["total_score"] == 8
    assert result["dimensions"] == [
        {"name": "\u7b2c1\u9898", "score": 8, "comment": "Good work"}
    ]


def _provider_grading_context(db_session, suffix: str) -> tuple[PaperSubmission, AnswerKey]:
    submission, answer_key = _grading_context(db_session, suffix)
    db_session.add(
        AiProvider(
            id=f"paper-ai-grading-provider-{suffix}",
            name=f"Paper AI grading provider {suffix}",
            api_url="https://provider.example/v1",
            model="grading-model",
            api_key="grading-key",
            status="active",
        )
    )
    db_session.flush()
    return submission, answer_key


def test_paper_grading_returns_timeout_when_ai_call_times_out(db_session, monkeypatch):
    submission, answer_key = _provider_grading_context(db_session, "timeout")

    def _raise(provider, prompt):
        raise httpx.TimeoutException("timeout")
    monkeypatch.setattr("app.modules.papers.ai_grading._call_evaluate_ai", _raise)

    result = evaluate_paper_submission(db_session, submission, answer_key)

    assert result["status"] == "unavailable"
    assert result["error_code"] == "timeout"
    assert submission.status == SubmissionStatus.PENDING
    assert submission.ai_score is None


def test_paper_grading_returns_invalid_output_when_ai_returns_unparseable(db_session, monkeypatch):
    submission, answer_key = _provider_grading_context(db_session, "invalid")

    monkeypatch.setattr(
        "app.modules.papers.ai_grading._call_evaluate_ai",
        lambda provider, prompt: None,
    )

    result = evaluate_paper_submission(db_session, submission, answer_key)

    assert result["status"] == "unavailable"
    assert result["error_code"] == "invalid_output"
    assert submission.status == SubmissionStatus.PENDING
    assert submission.ai_score is None
