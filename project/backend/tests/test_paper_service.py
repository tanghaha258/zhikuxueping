from app.modules.papers.service import (
    create_paper,
    count_papers,
    get_answer_key,
    get_paper,
    list_papers,
    update_paper,
    upsert_answer_key,
)
from app.schemas.paper import AnswerKeyUpsert, PaperCreate, PaperUpdate


def test_paper_service_creates_updates_and_lists_papers(db_session):
    paper = create_paper(
        db_session,
        PaperCreate(title="Service paper", class_ids=[]),
        teacher_id="service-teacher",
    )

    updated = update_paper(db_session, paper.id, PaperUpdate(title="Updated service paper"))

    assert updated.title == "Updated service paper"
    assert get_paper(db_session, paper.id) is updated
    assert [item.id for item in list_papers(db_session, teacher_id="service-teacher")] == [paper.id]
    assert count_papers(db_session, teacher_id="service-teacher") == 1


def test_paper_service_upserts_answer_key_and_calculates_score(db_session):
    paper = create_paper(
        db_session,
        PaperCreate(title="Answer key paper", class_ids=[]),
        teacher_id="answer-key-teacher",
    )
    data = AnswerKeyUpsert(
        questions=[
            {"index": 0, "type": "choice", "score": 5, "answer": "A"},
            {"index": 1, "type": "essay", "score": 10, "answer": "Explanation"},
        ]
    )

    answer_key = upsert_answer_key(db_session, paper.id, data)

    assert answer_key.total_score == 15
    assert get_answer_key(db_session, paper.id) is answer_key

    updated = upsert_answer_key(
        db_session,
        paper.id,
        AnswerKeyUpsert(questions=[], total_score=20),
    )
    assert updated.id == answer_key.id
    assert updated.total_score == 20
