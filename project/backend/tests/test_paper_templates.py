import json

import pytest

from app.modules.paper_generation.templates import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    sync_template_to_teacher,
    update_template,
    validate_template_sections,
)
from app.schemas.paper_generator import PaperTemplateCreate, PaperTemplateUpdate


def _template_data(name: str = "Template") -> PaperTemplateCreate:
    return PaperTemplateCreate(
        name=name,
        exam_type="quiz",
        subject="math",
        grade="7",
        total_score=10,
        sections=json.dumps([{"total": 10}]),
    )


def test_template_section_validation_rejects_mismatched_total():
    valid, _ = validate_template_sections(100, json.dumps([{"total": 90}]))

    assert valid is False


def test_template_lifecycle_persists_updates_and_soft_deletes(db_session):
    template = create_template(db_session, _template_data())

    updated = update_template(
        db_session,
        template.id,
        PaperTemplateUpdate(name="Updated template"),
    )

    assert updated.name == "Updated template"
    assert get_template(db_session, template.id) is updated
    assert template.id in {item.id for item in list_templates(db_session)}

    assert delete_template(db_session, template.id) is True
    assert template.id not in {item.id for item in list_templates(db_session)}


def test_sync_template_creates_an_independent_copy(db_session):
    template = create_template(db_session, _template_data("Original"))

    copied = sync_template_to_teacher(db_session, template.id, "teacher-1")

    assert copied.id != template.id
    assert copied.name == "Original (\u4e2a\u4eba)"
    assert copied.sections == template.sections


def test_create_template_rejects_invalid_sections(db_session):
    invalid = PaperTemplateCreate(
        name="Invalid template",
        subject="math",
        grade="7",
        total_score=100,
        sections=json.dumps([{"total": 90}]),
    )

    with pytest.raises(ValueError):
        create_template(db_session, invalid)
