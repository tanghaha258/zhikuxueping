"""AI-assisted grading for task submissions.

设计原则（与平台核心闭环一致）：
- 无可用 Provider 或调用失败时，返回明确的“不可用”状态，不写入 AI 分数或评价记录。
- 不产生随机模拟分数，不制造可采纳的虚假成功结果。
- 失败原因统一映射到 AiErrorCode，便于人工兜底与审计。
- AI 成功时只创建 `EvaluationRecord`（status=DRAFT, source=ai），
  作为教师待确认的草稿，不写入旧 `Evaluation` 表，不直接让学生可见。

核心闭环扩展（计划 Task 5）：
- `evaluate_submission_governed` 通过 AI 治理层（ai_jobs）创建评分任务，
  落库输出版本与质量问题，支持局部重生成与教师审核采用。
  保留 `evaluate_submission` 向后兼容旧入口。
"""

import json
import re
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_provider import AiProvider
from app.models.enums import (
    AiJobScene,
    EvaluationSource,
    EvaluationStatus,
    EvaluationSubjectType,
)
from app.models.evaluation_plan import EvaluationRecord
from app.models.project import Project, ProjectSubject
from app.models.submission import Submission
from app.models.subject import Subject
from app.models.task import Task
from app.models.user import User
from app.modules.ai_gateway import complete
from app.modules.ai_gateway.errors import AiErrorCode, unavailable_result
from app.modules.ai_jobs import service as ai_jobs_service
from app.shared.file_parsing import extract_text


def evaluate_submission(db: Session, submission_id: str, teacher_id: str) -> dict:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise ValueError("\u63d0\u4ea4\u8bb0\u5f55\u4e0d\u5b58\u5728")

    task = db.get(Task, submission.task_id)
    if not task:
        raise ValueError("\u4efb\u52a1\u4e0d\u5b58\u5728")

    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()
    if not provider:
        return unavailable_result(
            AiErrorCode.PROVIDER_UNAVAILABLE,
            "AI \u8bc4\u5206\u670d\u52a1\u4e0d\u53ef\u7528\uff0c\u8bf7\u914d\u7f6e Provider \u6216\u7531\u6559\u5e08\u4eba\u5de5\u590d\u6838\u3002",
        )

    try:
        result = _call_evaluate_ai(provider, _build_grading_prompt(db, submission, task))
    except httpx.TimeoutException:
        return unavailable_result(AiErrorCode.TIMEOUT, "AI \u8bc4\u5206\u8d85\u65f6\uff0c\u8bf7\u91cd\u8bd5\u6216\u4eba\u5de5\u590d\u6838\u3002")
    except (json.JSONDecodeError, ValueError):
        return unavailable_result(AiErrorCode.INVALID_OUTPUT, "AI \u8fd4\u56de\u7ed3\u6784\u65e0\u6548\uff0c\u65e0\u6cd5\u91c7\u7eb3\u8bc4\u5206\u3002")
    except Exception:
        return unavailable_result(AiErrorCode.PROVIDER_UNAVAILABLE, "AI \u8bc4\u5206\u8c03\u7528\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Provider \u914d\u7f6e\u3002")

    if not result:
        return unavailable_result(AiErrorCode.INVALID_OUTPUT, "AI \u672a\u8fd4\u56de\u53ef\u89e3\u6790\u7684\u8bc4\u5206\u7ed3\u679c\u3002")

    return _save_evaluation(db, submission, task, result, teacher_id)


def _build_grading_prompt(db: Session, submission: Submission, task: Task) -> str:
    subject_name = _subject_name(db, task.project_id)
    attachment_texts = []
    has_images = False
    for url in submission.file_urls or []:
        if url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            has_images = True
            continue
        text = extract_text(url)
        if text:
            attachment_texts.append(text)

    prompt_parts = [
        f"\u4f60\u662f\u4e00\u4f4d\u521d\u4e2d{subject_name}\u6559\u5e08\uff0c"
        "\u8bf7\u6839\u636e\u4ee5\u4e0b\u8bc4\u5206\u7ec6\u5219\u5bf9\u5b66\u751f\u4f5c\u4e1a\u8fdb\u884c\u8bc4\u5206\u3002",
        f"\n## \u4efb\u52a1\u4fe1\u606f\n\u9898\u76ee\uff1a{task.title}\n"
        f"\u63cf\u8ff0\uff1a{task.description or ''}",
    ]
    if task.rubric:
        prompt_parts.append(f"\n## \u8bc4\u5206\u7ec6\u5219\n{task.rubric}")
    prompt_parts.append(
        f"\n## \u5b66\u751f\u63d0\u4ea4\u5185\u5bb9\n{submission.content or ''}"
    )
    if attachment_texts:
        attachment_text = "\n".join(attachment_texts)
        prompt_parts.append(f"\n## \u9644\u4ef6\u6587\u672c\n{attachment_text}")
    if has_images:
        prompt_parts.append(
            "\n## \u56fe\u7247\u6750\u6599\n"
            "[\u5b66\u751f\u63d0\u4ea4\u4e86\u56fe\u7247\uff0c\u8bf7\u5206\u6790\u56fe\u7247\u5185\u5bb9]"
        )
    prompt_parts.append(
        "\n\u8bf7\u4e25\u683c\u6309\u4ee5\u4e0b JSON \u683c\u5f0f\u8f93\u51fa\uff0c"
        "\u4e0d\u8981\u5305\u542b\u5176\u4ed6\u5185\u5bb9\uff1a\n"
        '{"dimensions": [{"name": "\u7ef4\u5ea6\u540d", "score": 0, '
        '"comment": "\u8bc4\u8bed"}], "total_score": 0, '
        '"overall_comment": "\u603b\u4f53\u8bc4\u8bed"}'
    )
    return "\n".join(prompt_parts)


def _subject_name(db: Session, project_id: str) -> str:
    project = db.get(Project, project_id)
    if not project:
        return "\u8de8\u5b66\u79d1"
    statement = (
        select(Subject.name)
        .join(ProjectSubject, Subject.id == ProjectSubject.subject_id)
        .where(ProjectSubject.project_id == project_id)
    )
    return db.execute(statement).scalars().first() or "\u8de8\u5b66\u79d1"


def _call_evaluate_ai(provider: AiProvider, prompt: str) -> Optional[dict]:
    content = complete(
        provider.api_url,
        provider.api_key,
        provider.model,
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
        timeout=60.0,
    )
    json_match = re.search(r"\{.*\}", content, re.DOTALL)
    if not json_match:
        return None
    return json.loads(json_match.group())


def _save_evaluation(
    db: Session,
    submission: Submission,
    task: Task,
    result: dict,
    teacher_id: str,
) -> dict:
    """将 AI 评分结果落库为 `EvaluationRecord`（DRAFT, source=ai）。

    验收（计划 Task 2）：
    - AI 草稿创建 `EvaluationRecord`（status=DRAFT, source=AI），不写入旧 `Evaluation`。
    - 学生不可见未发布记录（状态机需教师确认后发布到 PUBLISHED）。
    - 返回新契约：``evaluation_record_id`` / ``status`` / ``source``，
      不再返回旧的 ``evaluation_id``。
    """
    total_score = result.get("total_score", 0)
    comment = result.get("overall_comment", "")
    record = EvaluationRecord(
        project_id=task.project_id,
        task_id=submission.task_id,
        student_id=submission.student_id,
        evaluator_id=teacher_id,
        subject_type=EvaluationSubjectType.TASK,
        subject_id=submission.task_id,
        source=EvaluationSource.AI,
        status=EvaluationStatus.DRAFT,
        total_score=total_score,
        comment=comment,
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
    except Exception:
        db.rollback()
        raise
    return {
        "status": "draft",
        "source": EvaluationSource.AI.value,
        "evaluation_record_id": record.id,
        "dimensions": result.get("dimensions", []),
        "total_score": total_score,
        "overall_comment": comment,
    }


# ── 治理层接入（计划 Task 5）────────────────────────────────
def evaluate_submission_governed(
    db: Session,
    actor: User,
    submission_id: str,
) -> dict[str, Any]:
    """通过 AI 治理层对提交进行评分（计划 Task 5）。

    创建 scene=GRADING 的 AI 任务，自动聚合项目上下文作为输入摘要，
    落库输出版本与质量问题。失败不产生模拟分数（Provider 不可用/超时/结构无效
    均映射为 FAILED）。
    返回 AI 任务详情（含版本、质量问题、阻断问题数）。
    """
    submission = db.get(Submission, submission_id)
    if not submission:
        raise ValueError("提交记录不存在")
    task = db.get(Task, submission.task_id)
    if not task:
        raise ValueError("任务不存在")

    job = ai_jobs_service.create_and_run_job(
        db,
        actor,
        task.project_id,
        AiJobScene.GRADING,
        "评分结果",
        task_id=task.id,
        submission_id=submission.id,
    )
    return ai_jobs_service.get_job_detail(db, actor, job.id)
