"""AI-assisted grading for paper submissions.

设计原则（与平台核心闭环一致）：
- 无可用 Provider 或调用失败时，返回明确的“不可用”状态，不写入 AI 分数、
  不将答卷标记为已批改，避免制造可采纳的虚假成功结果。
- 失败原因统一映射到 AiErrorCode，便于人工兜底与审计。
"""

import json
import re
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_provider import AiProvider
from app.models.paper import AnswerKey, PaperSubmission, SubmissionStatus
from app.modules.ai_gateway import complete
from app.modules.ai_gateway.errors import AiErrorCode, unavailable_result


def evaluate_paper_submission(
    db: Session,
    submission: PaperSubmission,
    answer_key: AnswerKey,
) -> dict:
    questions = answer_key.questions or []
    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()
    if not provider:
        return unavailable_result(
            AiErrorCode.PROVIDER_UNAVAILABLE,
            "AI \u6279\u6539\u670d\u52a1\u4e0d\u53ef\u7528\uff0c\u8bf7\u914d\u7f6e Provider \u6216\u7531\u6559\u5e08\u4eba\u5de5\u590d\u6838\u3002",
        )

    try:
        result = _call_evaluate_ai(provider, _build_grading_prompt(questions))
    except httpx.TimeoutException:
        return unavailable_result(AiErrorCode.TIMEOUT, "AI \u6279\u6539\u8d85\u65f6\uff0c\u8bf7\u91cd\u8bd5\u6216\u4eba\u5de5\u590d\u6838\u3002")
    except (json.JSONDecodeError, ValueError):
        return unavailable_result(AiErrorCode.INVALID_OUTPUT, "AI \u8fd4\u56de\u7ed3\u6784\u65e0\u6548\uff0c\u65e0\u6cd5\u91c7\u7eb3\u6279\u6539\u7ed3\u679c\u3002")
    except Exception:
        return unavailable_result(AiErrorCode.PROVIDER_UNAVAILABLE, "AI \u6279\u6539\u8c03\u7528\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Provider \u914d\u7f6e\u3002")

    if not result or not result.get("questions"):
        return unavailable_result(AiErrorCode.INVALID_OUTPUT, "AI \u672a\u8fd4\u56de\u53ef\u7528\u7684\u6279\u6539\u7ed3\u679c\u3002")

    return _save_ai_result(db, submission, result)


def _build_grading_prompt(questions: list) -> str:
    question_texts = []
    for question in questions:
        question_texts.append(
            f"\u7b2c{question.get('index', 0) + 1}\u9898"
            f"\uff08{question.get('score', 0)}\u5206\uff09\uff1a{question.get('content', '')}\n"
            f"\u53c2\u8003\u7b54\u6848\uff1a{question.get('answer', '')}\n"
            f"\u5b66\u751f\u7b54\u6848\uff1a{question.get('student_answer', '\u672a\u63d0\u4ea4')}"
        )
    return (
        "\u4f60\u662f\u4e00\u4f4d\u521d\u4e2d\u6559\u5e08\uff0c"
        "\u8bf7\u6839\u636e\u53c2\u8003\u7b54\u6848\u5bf9\u5b66\u751f\u7684\u8bd5\u5377\u7b54\u6848\u8fdb\u884c\u8bc4\u5206\u3002\n\n"
        + "\n\n".join(question_texts)
        + "\n\n\u8bf7\u4e25\u683c\u6309\u4ee5\u4e0b JSON \u683c\u5f0f\u8f93\u51fa\uff0c"
        "\u4e0d\u8981\u5305\u542b\u5176\u4ed6\u5185\u5bb9\uff1a\n"
        '{"questions": [{"index": 1, "score": \u5206\u6570, '
        '"comment": "\u8bc4\u8bed"}], "total_score": \u603b\u5206, '
        '"overall_comment": "\u603b\u4f53\u8bc4\u8bed"}'
    )


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


def _save_ai_result(db: Session, submission: PaperSubmission, result: dict) -> dict:
    dimensions = []
    total_score = 0
    for question_result in result["questions"]:
        score = question_result.get("score", 0)
        total_score += score
        dimensions.append(
            {
                "name": f"\u7b2c{question_result.get('index', 0)}\u9898",
                "score": score,
                "comment": question_result.get("comment", ""),
            }
        )

    final_score = round(total_score, 1)
    comment = result.get("overall_comment", "AI \u81ea\u52a8\u6279\u6539\u5b8c\u6210")
    submission.ai_score = final_score
    submission.ai_comment = comment
    submission.status = SubmissionStatus.GRADED
    db.commit()
    return {
        "status": "succeeded",
        "dimensions": dimensions,
        "total_score": final_score,
        "overall_comment": result.get(
            "overall_comment",
            "\u7b54\u5377\u5df2\u7531 AI \u81ea\u52a8\u6279\u6539\u5b8c\u6210\uff0c"
            "\u8bf7\u6559\u5e08\u590d\u6838\u3002",
        ),
    }
