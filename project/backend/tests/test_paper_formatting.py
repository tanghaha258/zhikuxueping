import json

import pytest

from app.models.paper_template import AiGeneratedPaper
from app.modules.paper_generation.formatting import (
    format_paper,
    get_formatted_paper,
    update_formatted_paper,
)


def _paper(paper_id: str = "formatting-paper") -> AiGeneratedPaper:
    return AiGeneratedPaper(
        id=paper_id,
        teacher_id="formatting-teacher",
        subject="math",
        grade="7",
        title="Formatting Paper",
        questions=json.dumps(
            [
                {
                    "type": "choice",
                    "content": "What is 1 + 1?",
                    "options": ["1", "2"],
                    "score": 5,
                }
            ]
        ),
        total_score=5,
        duration=30,
    )


def test_format_paper_renders_and_persists_html(db_session):
    paper = _paper()
    db_session.add(paper)
    db_session.flush()

    formatted = format_paper(db_session, paper.id, "quiz", "math")

    assert formatted.template_type == "quiz"
    assert formatted.formatted_html.startswith("<!DOCTYPE html>")
    assert "Formatting Paper" in formatted.formatted_html
    assert get_formatted_paper(db_session, paper.id) is formatted


def test_get_formatted_paper_returns_none_before_formatting(db_session):
    paper = _paper("unformatted-paper")
    db_session.add(paper)
    db_session.flush()

    assert get_formatted_paper(db_session, paper.id) is None


def test_update_formatted_paper_persists_html_and_template_config(db_session):
    paper = _paper("editable-formatted-paper")
    db_session.add(paper)
    db_session.flush()

    updated = update_formatted_paper(
        db_session,
        paper.id,
        "<html><body>edited</body></html>",
        '{"font_size": 12}',
    )

    assert updated.formatted_html == "<html><body>edited</body></html>"
    assert updated.template_config == '{"font_size": 12}'


def test_format_paper_rejects_missing_paper(db_session):
    with pytest.raises(ValueError, match="paper not found"):
        format_paper(db_session, "missing-paper", "quiz", "math")
