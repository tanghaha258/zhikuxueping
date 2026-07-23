import pytest
from types import SimpleNamespace

from app.modules.paper_generation.composition import (
    compose_questions,
    parse_sections,
    pick_from_bank,
    question_to_paper_question,
)
from app.models.question import Question


def test_parse_sections_rejects_invalid_json():
    with pytest.raises(ValueError, match="sections"):
        parse_sections("not-json")


def test_compose_questions_keeps_same_type_sections_separate():
    sections = [
        {"type": "choice", "count": 1, "score_per": 2},
        {"type": "choice", "count": 1, "score_per": 3},
    ]

    questions = compose_questions(
        sections,
        bank_ratio=1.0,
        bank_questions_by_section=[
            [{"type": "choice", "content": "first", "score": 2, "_from_bank": True}],
            [{"type": "choice", "content": "second", "score": 3, "_from_bank": True}],
        ],
        ai_questions=[],
    )

    assert [(q["index"], q["content"], q["score"]) for q in questions] == [
        (1, "first", 2),
        (2, "second", 3),
    ]


def test_question_to_paper_question_keeps_identity_and_section_score():
    question = SimpleNamespace(
        id="q-1",
        content="content",
        options='["A", "B"]',
        answer="A",
        analysis="why",
    )

    result = question_to_paper_question(question, "choice", 8)

    assert result["_question_id"] == "q-1"
    assert result["score"] == 8
    assert result["options"] == ["A", "B"]


def test_question_to_paper_question_ignores_invalid_options_json():
    question = SimpleNamespace(
        id="q-1",
        content="content",
        options="not-json",
        answer="A",
        analysis="why",
    )

    result = question_to_paper_question(question, "choice", 8)

    assert result["content"] == "content"
    assert result["options"] is None


def test_pick_from_bank_returns_only_published_matching_questions(db_session):
    matching = Question(
        id="matching", subject="composition-test", grade="7", question_type="choice",
        difficulty=3, content="matching", created_by="teacher", status="published",
    )
    archived = Question(
        id="archived", subject="composition-test", grade="7", question_type="choice",
        difficulty=3, content="archived", created_by="teacher", status="archived",
    )
    wrong_difficulty = Question(
        id="wrong-difficulty", subject="composition-test", grade="7", question_type="choice",
        difficulty=5, content="wrong difficulty", created_by="teacher", status="published",
    )
    db_session.add_all([matching, archived, wrong_difficulty])
    db_session.flush()

    questions = pick_from_bank(
        db_session, "composition-test", "7", "choice", "medium", None, count=10
    )

    assert [question.id for question in questions] == ["matching"]


def test_pick_from_bank_applies_visibility_filter(db_session):
    visible = Question(
        id="visible", subject="composition-visibility", grade="7", question_type="choice",
        difficulty=3, content="visible", created_by="visible-owner", status="published",
    )
    hidden = Question(
        id="hidden", subject="composition-visibility", grade="7", question_type="choice",
        difficulty=3, content="hidden", created_by="hidden-owner", status="published",
    )
    db_session.add_all([visible, hidden])
    db_session.flush()

    questions = pick_from_bank(
        db_session,
        "composition-visibility",
        "7",
        "choice",
        "medium",
        None,
        count=10,
        visibility_filter=Question.created_by == "visible-owner",
    )

    assert [question.id for question in questions] == ["visible"]
