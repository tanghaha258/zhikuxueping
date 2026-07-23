from app.modules.ai_gateway.client import complete, extract_content
from pathlib import Path


def test_extract_content_uses_reasoning_when_content_is_empty():
    data = {
        "choices": [
            {"message": {"content": "", "reasoning_content": "备用答案"}}
        ]
    }

    assert extract_content(data) == "备用答案"


def test_complete_posts_to_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "模型答案"}}]}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.modules.ai_gateway.client.httpx.post", fake_post)

    content = complete(
        "https://model.example/v1/",
        "provider-key",
        "test-model",
        [{"role": "user", "content": "你好"}],
        temperature=0.2,
        max_tokens=128,
        timeout=12.0,
    )

    assert content == "模型答案"
    assert captured["url"] == "https://model.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer provider-key"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["stream"] is False
    assert captured["timeout"] == 12.0


def test_feature_services_do_not_own_model_transport():
    services_dir = Path(__file__).parents[1] / "app" / "services"
    for filename in ("ai.py", "question_bank.py", "paper_generator.py"):
        source = (services_dir / filename).read_text(encoding="utf-8")
        assert "import httpx" not in source
        assert "/chat/completions" not in source
