import importlib.util
from uuid import uuid4

from app.schemas.question_bank import AiGenerateRequest, QuestionCreate
from app.models.question import Question


def test_legacy_question_bank_router_reexports_module_router():
    assert importlib.util.find_spec("app.modules.question_bank.router") is not None

    from app.api.v1 import question_bank
    from app.modules.question_bank import router

    assert question_bank.router is router.router


def test_question_bank_service_persists_creator(db_session):
    from app.modules.question_bank import service

    question = service.create_question(
        db_session,
        QuestionCreate(
            subject="math",
            grade="7",
            question_type="choice",
            content="What is 1 + 1?",
            answer="2",
        ),
        user_id="question-module-owner",
    )

    loaded = service.get_question(db_session, question.id)
    assert loaded is not None
    assert loaded.created_by == "question-module-owner"
    assert loaded.content == "What is 1 + 1?"


def test_quality_statistics_preserve_existing_archived_record_semantics(db_session):
    from app.modules.question_bank import service

    subject = f"archived-subject-{uuid4().hex}"
    question = Question(
        subject=subject,
        grade="7",
        question_type="choice",
        content="Archived question",
        created_by="question-module-owner",
        status="archived",
        quality_level="excellent",
        difficulty_calibrated=0.8,
        discrimination=0.6,
    )
    db_session.add(question)
    db_session.commit()

    stats = service.get_quality_stats(db_session, subject=subject)

    assert stats["total_questions"] == 0
    assert stats["quality_distribution"]["excellent"] == 1
    assert stats["avg_difficulty"] == 0.8
    assert stats["avg_discrimination"] == 0.6


def test_ai_generation_prompt_preserves_chinese_teaching_context():
    from app.modules.question_bank import service

    prompt = service.build_generation_prompt(
        AiGenerateRequest(
            subject="数学",
            grade="七年级",
            question_type="选择题",
            knowledge_points=["有理数"],
            count=2,
            difficulty=3,
        )
    )

    assert "你是一位初中数学教师" in prompt
    assert "七年级学生生成2道选择题" in prompt
    assert "知识点范围：有理数" in prompt
    assert "严格按以下 JSON 格式输出" in prompt
