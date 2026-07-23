"""Formatting persistence for generated papers."""

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models.paper_template import AiGeneratedPaper
from app.modules.paper_generation.renderer import render_exam_paper


def _get_paper(db: Session, paper_id: str) -> Optional[AiGeneratedPaper]:
    return db.get(AiGeneratedPaper, paper_id)


def format_paper(
    db: Session,
    paper_id: str,
    template_type: str,
    subject: str,
) -> AiGeneratedPaper:
    paper = _get_paper(db, paper_id)
    if not paper:
        raise ValueError("paper not found")

    questions = json.loads(paper.questions or "[]")
    knowledge_points = json.loads(paper.knowledge_points or "[]")
    paper.formatted_html = render_exam_paper(
        paper.title,
        questions,
        paper.total_score,
        paper.duration,
        template_type=template_type,
        subject=subject or paper.subject,
        knowledge_points=knowledge_points,
    )
    paper.template_type = template_type
    db.commit()
    db.refresh(paper)
    return paper


def get_formatted_paper(db: Session, paper_id: str) -> Optional[AiGeneratedPaper]:
    paper = _get_paper(db, paper_id)
    if not paper or not paper.formatted_html:
        return None
    return paper


def update_formatted_paper(
    db: Session,
    paper_id: str,
    formatted_html: str,
    template_config: Optional[str] = None,
) -> AiGeneratedPaper:
    paper = _get_paper(db, paper_id)
    if not paper:
        raise ValueError("paper not found")

    paper.formatted_html = formatted_html
    if template_config:
        paper.template_config = template_config
    db.commit()
    db.refresh(paper)
    return paper
