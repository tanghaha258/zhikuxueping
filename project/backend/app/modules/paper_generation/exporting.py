"""HTML export for generated papers."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.paper_template import AiGeneratedPaper


_TYPE_LABELS = {
    "choice": "\u9009\u62e9\u9898",
    "fill": "\u586b\u7a7a\u9898",
    "essay": "\u7b80\u7b54\u9898",
    "judge": "\u5224\u65ad\u9898",
    "reading": "\u9605\u8bfb\u7406\u89e3",
    "cloze": "\u5b8c\u5f62\u586b\u7a7a",
    "writing": "\u5199\u4f5c",
    "classical": "\u6587\u8a00\u6587",
    "calculate": "\u8ba1\u7b97\u9898",
    "proof": "\u8bc1\u660e\u9898",
    "experiment": "\u5b9e\u9a8c\u9898",
    "material": "\u6750\u6599\u5206\u6790",
}


def export_paper(db: Session, paper_id: str, fmt: str = "html") -> str:
    paper = db.get(AiGeneratedPaper, paper_id)
    if not paper:
        raise ValueError("\u8bd5\u5377\u4e0d\u5b58\u5728")
    if fmt != "html":
        raise ValueError(f"\u4e0d\u652f\u6301\u7684\u5bfc\u51fa\u683c\u5f0f: {fmt}")
    return render_export_html(paper)


def render_export_html(paper: Any) -> str:
    questions = _load_questions(paper.questions)
    knowledge_points = _load_knowledge_points(paper.knowledge_points)
    knowledge_points_html = ""
    if knowledge_points:
        knowledge_points_html = (
            '<p style="text-align:center;color:#666;font-size:13px;margin-top:4px;">'
            f"\u77e5\u8bc6\u70b9\uff1a{'\u3001'.join(knowledge_points)}</p>"
        )

    question_html = ""
    answer_html = ""
    for index, question in enumerate(questions, 1):
        question_html += _render_question_html(question, index)
        answer_html += f"""
        <div style="margin-bottom:12px;padding:10px 14px;border-left:3px solid #409eff;background:#f6f8fa;border-radius:4px;">
            <div style="font-weight:600;margin-bottom:4px;">\u7b2c{index}\u9898</div>
            <div style="margin:4px 0;"><strong>\u7b54\u6848\uff1a</strong>{question.get('answer', '')}</div>
            <div style="margin:4px 0;"><strong>\u89e3\u6790\uff1a</strong>{question.get('analysis', '')}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{paper.title}</title>
<style>
  @media print {{ body {{ padding:0 !important; }} }}
  body {{ font-family: 'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif; max-width:210mm; margin:0 auto; padding:20mm 15mm; color:#1a1a1a; }}
  h1 {{ font-size:22px; text-align:center; margin-bottom:4px; }}
  .paper-meta {{ text-align:center; color:#666; font-size:14px; margin-bottom:20px; }}
  hr {{ border:none; border-top:2px solid #333; margin:16px 0; }}
  .answer-section h2 {{ font-size:18px; border-bottom:2px solid #333; padding-bottom:6px; }}
</style>
</head>
<body>
<h1>{paper.title}</h1>
{knowledge_points_html}
<div class="paper-meta">
  <span>\u603b\u5206\uff1a<strong>{paper.total_score}</strong> \u5206</span>
  <span style="margin-left:20px;">\u65f6\u957f\uff1a<strong>{paper.duration}</strong> \u5206\u949f</span>
</div>
<hr>
<div class="question-section">
  {question_html}
</div>
<hr class="answer-section">
<div class="answer-section">
  <h2>\u53c2\u8003\u7b54\u6848\u4e0e\u89e3\u6790</h2>
  {answer_html}
</div>
</body></html>"""


def _load_questions(raw_questions: Any) -> list[dict]:
    try:
        questions = json.loads(raw_questions or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    return questions if isinstance(questions, list) else []


def _load_knowledge_points(raw_knowledge_points: Any) -> list[str]:
    try:
        knowledge_points = json.loads(raw_knowledge_points or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(knowledge_points, list):
        return []
    return [str(point) for point in knowledge_points]


def _render_question_html(question: dict, index: int) -> str:
    type_label = _TYPE_LABELS.get(question.get("type", ""), question.get("type", ""))
    options_html = _render_options_html(question.get("options"))
    return f"""
    <div style="margin-bottom:20px;padding:16px 20px;border:1px solid #d9d9d9;border-radius:6px;page-break-inside:avoid;">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;color:#1a1a1a;">
            {index}. [{type_label}]\uff08{question.get('score', 0)}\u5206\uff09
        </div>
        <div style="font-size:14px;line-height:1.8;color:#333;">{question.get('content', '')}</div>
        {options_html}
    </div>"""


def _render_options_html(options: Any) -> str:
    if isinstance(options, str):
        try:
            options = json.loads(options)
        except (json.JSONDecodeError, TypeError):
            return f'<div style="margin:8px 0 8px 24px;">{options}</div>'
    if not isinstance(options, list):
        return ""

    html = '<div style="margin:8px 0 8px 24px;">'
    for option in options:
        if isinstance(option, dict):
            html += (
                '<div style="margin:4px 0;">'
                f"{option.get('label', '')}. {option.get('content', '')}</div>"
            )
        elif isinstance(option, str):
            html += f'<div style="margin:4px 0;">{option}</div>'
    return f"{html}</div>"
