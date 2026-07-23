from app.modules.paper_generation.streaming_parser import (
    extract_question_from_buffer,
    find_complete_json,
)


def test_extract_question_preserves_braces_inside_content():
    buffer = '{"questions":[{"index":1,"type":"essay","content":"Use {x} safely","score":5}]}'

    question = extract_question_from_buffer(buffer, 0)

    assert question == {"index": 1, "type": "essay", "content": "Use {x} safely", "score": 5}


def test_extract_question_returns_none_until_json_object_is_complete():
    buffer = '{"questions":[{"index":1,"content":"incomplete"'

    assert extract_question_from_buffer(buffer, 0) is None


def test_find_complete_json_ignores_braces_inside_strings():
    buffer = '{"title":"{draft}","questions":[]} trailing response'

    assert find_complete_json(buffer) == {"title": "{draft}", "questions": []}
