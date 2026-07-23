import json
from types import SimpleNamespace

import pytest

from app.models.paper_template import AiGeneratedPaper
from app.modules.paper_generation.exporting import export_paper, render_export_html


def _paper_data() -> dict:
    return {
        "title": "Export Paper",
        "questions": json.dumps(
            [
                {
                    "type": "choice",
                    "content": "Which number is even?",
                    "options": [
                        {"label": "A", "content": "3"},
                        {"label": "B", "content": "4"},
                    ],
                    "answer": "B",
                    "analysis": "4 is divisible by 2.",
                    "score": 5,
                }
            ]
        ),
        "knowledge_points": json.dumps(["Numbers"]),
        "total_score": 5,
        "duration": 30,
    }


def test_render_export_html_includes_question_options_and_answer():
    paper = SimpleNamespace(**_paper_data())

    html = render_export_html(paper)

    assert html.startswith("<!DOCTYPE html>")
    assert "Export Paper" in html
    assert "Which number is even?" in html
    assert "A. 3" in html
    assert "B. 4" in html
    assert "4 is divisible by 2." in html
    assert "Numbers" in html


def test_export_paper_loads_the_stored_paper(db_session):
    paper = AiGeneratedPaper(
        id="exported-paper",
        teacher_id="export-teacher",
        subject="math",
        grade="7",
        **_paper_data(),
    )
    db_session.add(paper)
    db_session.flush()

    html = export_paper(db_session, paper.id)

    assert "Export Paper" in html


def test_export_paper_rejects_unsupported_format(db_session):
    paper = AiGeneratedPaper(
        id="unsupported-export-paper",
        teacher_id="export-teacher",
        subject="math",
        grade="7",
        **_paper_data(),
    )
    db_session.add(paper)
    db_session.flush()

    with pytest.raises(ValueError, match="\u4e0d\u652f\u6301\u7684\u5bfc\u51fa\u683c\u5f0f"):
        export_paper(db_session, paper.id, "pdf")
