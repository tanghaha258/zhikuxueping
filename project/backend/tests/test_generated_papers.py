from sqlalchemy import select

from app.models.paper import Paper
from app.models.paper_template import AiGeneratedPaper
from app.modules.paper_generation.papers import (
    count_generated_papers,
    delete_generated_paper,
    finalize_paper,
    get_generated_paper,
    list_generated_papers,
    update_generated_paper,
)
from app.schemas.paper_generator import AiGeneratedPaperUpdate


def _paper(paper_id: str, teacher_id: str = "paper-owner") -> AiGeneratedPaper:
    return AiGeneratedPaper(
        id=paper_id,
        teacher_id=teacher_id,
        subject="math",
        grade="7",
        title=f"Paper {paper_id}",
        questions="[]",
        total_score=100,
        duration=90,
    )


def test_list_and_count_generated_papers_are_scoped_to_teacher(db_session):
    owned_first = _paper("owned-first")
    owned_second = _paper("owned-second")
    other = _paper("other-paper", teacher_id="other-teacher")
    db_session.add_all([owned_first, owned_second, other])
    db_session.flush()

    papers = list_generated_papers(db_session, "paper-owner")

    assert {paper.id for paper in papers} == {"owned-first", "owned-second"}
    assert count_generated_papers(db_session, "paper-owner") == 2
    assert get_generated_paper(db_session, "other-paper") is other


def test_update_generated_paper_applies_only_provided_fields(db_session):
    paper = _paper("editable-paper")
    db_session.add(paper)
    db_session.flush()

    updated = update_generated_paper(
        db_session,
        paper.id,
        AiGeneratedPaperUpdate(title="Updated title"),
    )

    assert updated.title == "Updated title"
    assert updated.duration == 90


def test_finalize_paper_creates_only_one_paper_record(db_session):
    paper = _paper("finalized-paper")
    db_session.add(paper)
    db_session.flush()

    assert finalize_paper(db_session, paper.id).status == "finalized"
    assert finalize_paper(db_session, paper.id).status == "finalized"

    records = db_session.execute(
        select(Paper).where(Paper.teacher_id == paper.teacher_id, Paper.title == paper.title)
    ).scalars().all()
    assert len(records) == 1


def test_delete_generated_paper_reports_whether_a_paper_existed(db_session):
    paper = _paper("deletable-paper")
    db_session.add(paper)
    db_session.flush()

    assert delete_generated_paper(db_session, paper.id) is True
    assert delete_generated_paper(db_session, paper.id) is False
