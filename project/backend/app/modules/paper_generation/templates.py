"""Template validation and persistence for paper generation."""

import json
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.paper_template import PaperTemplate
from app.repositories.base import BaseRepository


def validate_template_sections(
    total_score: float,
    sections_json: Optional[str],
) -> tuple[bool, str]:
    if not sections_json:
        return True, ""
    try:
        sections = json.loads(sections_json)
    except json.JSONDecodeError:
        return False, "sections \u683c\u5f0f\u65e0\u6548"

    if not isinstance(sections, list):
        return False, "sections \u5fc5\u987b\u662f JSON \u6570\u7ec4"
    calculated_total = sum(section.get("total", 0) for section in sections)
    if abs(calculated_total - total_score) > 0.01:
        return False, (
            f"\u9898\u578b\u5206\u503c\u52a0\u603b ({calculated_total}) "
            f"\u4e0e\u603b\u5206 ({total_score}) \u4e0d\u4e00\u81f4"
        )
    return True, ""


def create_template(db: Session, data) -> PaperTemplate:
    valid, message = validate_template_sections(data.total_score, data.sections)
    if not valid:
        raise ValueError(message)

    template = PaperTemplate(
        name=data.name,
        exam_type=data.exam_type,
        subject=data.subject,
        grade=data.grade,
        total_score=data.total_score,
        config=data.config,
        sections=data.sections,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def list_templates(db: Session, skip: int = 0, limit: int = 100) -> list[PaperTemplate]:
    statement = (
        select(PaperTemplate)
        .where(PaperTemplate.is_active.is_(True))
        .order_by(PaperTemplate.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def count_templates(db: Session) -> int:
    statement = (
        select(func.count())
        .select_from(PaperTemplate)
        .where(PaperTemplate.is_active.is_(True))
    )
    return db.execute(statement).scalar() or 0


def get_template(db: Session, template_id: str) -> Optional[PaperTemplate]:
    return BaseRepository(db, PaperTemplate).get_by_id(template_id)


def update_template(db: Session, template_id: str, data) -> PaperTemplate:
    repository = BaseRepository(db, PaperTemplate)
    template = repository.get_by_id(template_id)
    if not template:
        raise ValueError("\u6a21\u677f\u4e0d\u5b58\u5728")

    update_data = data.model_dump(exclude_unset=True)
    if "sections" in update_data or "total_score" in update_data:
        total_score = update_data.get("total_score", template.total_score)
        sections = update_data.get("sections", template.sections)
        valid, message = validate_template_sections(total_score, sections)
        if not valid:
            raise ValueError(message)
    return repository.update(template, update_data)


def sync_template_to_teacher(
    db: Session,
    template_id: str,
    teacher_id: str,
) -> PaperTemplate:
    del teacher_id
    original = get_template(db, template_id)
    if not original:
        raise ValueError("\u6a21\u677f\u4e0d\u5b58\u5728")

    template = PaperTemplate(
        name=f"{original.name} (\u4e2a\u4eba)",
        exam_type=original.exam_type,
        subject=original.subject,
        grade=original.grade,
        total_score=original.total_score,
        config=original.config,
        sections=original.sections,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: str) -> bool:
    template = BaseRepository(db, PaperTemplate).get_by_id(template_id)
    if not template:
        return False
    template.is_active = False
    db.commit()
    return True
