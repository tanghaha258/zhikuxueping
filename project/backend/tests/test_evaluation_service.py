"""评价服务层测试（计划 Task 2）。

Task 2 调整：
- 旧 `create_evaluation`/`update_evaluation` 已下线为只读兼容，调用即抛弃用错误，
  防止新数据继续写入旧 `Evaluation` 表。
- 只读函数（list/get）保留，用于展示旧版历史评价。
"""
import pytest

from app.core.exceptions import AppException
from app.models.evaluation import Evaluation
from app.modules.evaluations.service import (
    create_evaluation,
    get_evaluation,
    list_evaluations_by_student,
    list_evaluations_by_task,
    update_evaluation,
)
from app.schemas.evaluation import EvaluationCreate, EvaluationUpdate


def _seed_legacy_evaluation(db_session, task_id="evaluation-task",
                            student_id="student-1") -> Evaluation:
    """直接构造旧版评价记录（绕过已弃用的写入入口）。"""
    evaluation = Evaluation(
        task_id=task_id,
        student_id=student_id,
        evaluator_id="teacher-1",
        score=80,
        comment="Initial comment",
        eval_type="teacher",
        is_legacy=True,
    )
    db_session.add(evaluation)
    db_session.commit()
    db_session.refresh(evaluation)
    return evaluation


def test_create_evaluation_is_deprecated(db_session):
    """旧写入入口已下线：调用即抛弃用错误，不写入旧表。"""
    with pytest.raises(AppException) as exc:
        create_evaluation(db_session, _evaluation_data(), "teacher-1")
    assert exc.value.status_code == 410
    assert "已弃用" in exc.value.message or "evaluation-plans" in exc.value.message
    assert db_session.query(Evaluation).filter_by(task_id="evaluation-task").count() == 0


def test_update_evaluation_is_deprecated(db_session):
    """旧更新入口已下线：调用即抛弃用错误。"""
    evaluation = _seed_legacy_evaluation(db_session)
    with pytest.raises(AppException) as exc:
        update_evaluation(
            db_session,
            evaluation.id,
            EvaluationUpdate(score=95, comment="Updated comment"),
        )
    assert exc.value.status_code == 410
    # 原记录未被修改
    db_session.refresh(evaluation)
    assert evaluation.score == 80
    assert evaluation.comment == "Initial comment"


def test_list_and_get_legacy_evaluations_still_work(db_session):
    """只读路径保留：旧版历史评价仍可读取。"""
    first = _seed_legacy_evaluation(db_session, student_id="student-1")
    second = _seed_legacy_evaluation(
        db_session, task_id="evaluation-task", student_id="student-2"
    )

    assert get_evaluation(db_session, first.id) is first
    task_evaluation_ids = {
        item.id for item in list_evaluations_by_task(db_session, "evaluation-task")
    }
    student_evaluation_ids = {
        item.id for item in list_evaluations_by_student(db_session, "student-1")
    }

    assert {first.id, second.id}.issubset(task_evaluation_ids)
    assert first.id in student_evaluation_ids
    assert second.id not in student_evaluation_ids


def _evaluation_data(student_id: str = "student-1") -> EvaluationCreate:
    return EvaluationCreate(
        task_id="evaluation-task",
        student_id=student_id,
        score=80,
        comment="Initial comment",
        eval_type="teacher",
    )
