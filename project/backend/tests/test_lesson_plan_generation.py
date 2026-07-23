import asyncio

from app.models.ai_provider import AiProvider
from app.modules.lesson_plans.ai_generation import generate_lesson_plan


def test_lesson_plan_generation_uses_local_fallback_without_active_provider(db_session):
    result = asyncio.run(
        generate_lesson_plan(
            subject="science",
            grade="grade-7",
            topic="photosynthesis",
            duration=45,
            db=db_session,
        )
    )

    assert "photosynthesis" in result["title"]
    assert "photosynthesis" in result["content"]
    assert "<html>" in result["content"]
    # 本地模板必须标记来源与审核状态，不能被当作正式 AI 成果发布。
    assert result["source"] == "local_fallback"
    assert result["review_status"] == "draft"


def test_lesson_plan_generation_uses_active_provider_result(db_session, monkeypatch):
    db_session.add(
        AiProvider(
            id="lesson-plan-generation-provider",
            name="Lesson plan provider",
            api_url="https://provider.example/v1",
            model="lesson-plan-model",
            api_key="lesson-plan-key",
            status="active",
        )
    )
    db_session.flush()

    async def fake_generate_from_ai(*args, **kwargs):
        return {"title": "AI lesson plan", "content": "<p>AI result</p>"}

    monkeypatch.setattr(
        "app.modules.lesson_plans.ai_generation._generate_from_ai",
        fake_generate_from_ai,
    )

    result = asyncio.run(
        generate_lesson_plan(
            subject="science",
            grade="grade-7",
            topic="ecosystem",
            duration=45,
            db=db_session,
        )
    )

    assert result["title"] == "AI lesson plan"
    assert result["content"] == "<p>AI result</p>"
    # AI 生成内容默认待审核，标记来源为 ai。
    assert result["source"] == "ai"
    assert result["review_status"] == "draft"
