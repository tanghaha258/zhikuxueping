from app.modules.paper_generation.prompt_renderer import render_prompt


def test_render_prompt_replaces_variables_and_normalizes_json_braces():
    template = 'Subject: {subject}; {{"title":"{subject}"}}'

    prompt = render_prompt(template, {"subject": "math"})

    assert prompt == 'Subject: math; {"title":"math"}'


def test_render_prompt_replaces_default_question_examples():
    template = """{
"questions": [
  {"index": 1, "type": "placeholder", "score": 5, "content": "first", "analysis": "one"},
  {"index": 2, "type": "placeholder", "score": 5, "content": "second", "analysis": "two"},
  {"index": 3, "type": "placeholder", "score": 5, "content": "third", "analysis": "three"}
]
}"""

    prompt = render_prompt(template, {}, example_json='{"index": 1, "type": "choice", "content": "example"}')

    assert '"type": "choice"' in prompt
    assert "placeholder" not in prompt
