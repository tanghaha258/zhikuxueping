"""AI generation and local fallback for lesson plans.

核心闭环扩展（计划 Task 5 验收标准 4）：
- `generate_lesson_plan_from_project` 读取项目结构化上下文（真实问题、学科贡献、
  目标、指标、资源、任务、量规）作为 AI 输入，不由页面重复录入。
- 通过 AI 治理层（ai_jobs.service.create_and_run_job）创建任务，落库输出版本与
  质量问题，支持局部重生成与教师审核采用。
- 保留 `generate_lesson_plan` 向后兼容旧入口（表单输入），不删除已有行为。
"""

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_provider import AiProvider
from app.models.enums import AiJobScene
from app.models.user import User
from app.modules.ai_gateway import complete_async
from app.modules.ai_jobs import service as ai_jobs_service


async def generate_lesson_plan(
    subject: str,
    grade: str,
    topic: str,
    duration: int = 45,
    objectives: Optional[str] = None,
    additional: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    provider = None
    if db:
        provider = db.execute(
            select(AiProvider).where(AiProvider.status == "active")
        ).scalars().first()
    if provider:
        try:
            result = await _generate_from_ai(
                provider.api_url,
                provider.api_key,
                provider.model,
                subject,
                grade,
                topic,
                duration,
                objectives,
                additional,
            )
            return _tag_lesson_plan(result, source="ai", review_status="draft")
        except Exception:
            pass

    if settings.AI_API_BASE_URL and settings.AI_API_KEY:
        try:
            result = await _generate_from_ai(
                settings.AI_API_BASE_URL,
                settings.AI_API_KEY,
                settings.AI_MODEL,
                subject,
                grade,
                topic,
                duration,
                objectives,
                additional,
            )
            return _tag_lesson_plan(result, source="ai", review_status="draft")
        except Exception:
            pass

    return _tag_lesson_plan(
        _fallback_lesson_plan(subject, grade, topic, duration, objectives, additional),
        source="local_fallback",
        review_status="draft",
    )


def _tag_lesson_plan(result: dict, *, source: str, review_status: str) -> dict:
    """标注教案来源与审核状态，避免本地模板被当作正式 AI 成果发布。"""
    tagged = dict(result)
    tagged["source"] = source
    tagged["review_status"] = review_status
    return tagged


async def _generate_from_ai(
    api_url: str,
    api_key: str,
    model: str,
    subject: str,
    grade: str,
    topic: str,
    duration: int,
    objectives: Optional[str],
    additional: Optional[str],
) -> dict:
    prompt = (
        f"\u4f60\u662f\u4e00\u4f4d\u7ecf\u9a8c\u4e30\u5bcc\u7684\u521d\u4e2d{subject}\u6559\u5e08\uff0c"
        f"\u8bf7\u4e3a{grade}\u5b66\u751f\u8bbe\u8ba1\u4e00\u4efd\u5173\u4e8e\u300a{topic}\u300b\u7684\u5b8c\u6574\u6559\u6848\u3002\n"
        f"\u8bfe\u65f6\u957f\u5ea6\uff1a{duration}\u5206\u949f\u3002\n"
        f"\u6559\u5b66\u76ee\u6807\uff1a{objectives or '\u8bf7\u81ea\u884c\u8bbe\u5b9a'}\u3002\n"
        f"\u989d\u5916\u8981\u6c42\uff1a{additional or '\u65e0'}\u3002\n\n"
        "\u8bf7\u4ee5 HTML \u683c\u5f0f\u8f93\u51fa\uff0c\u5305\u542b\uff1a\n"
        "1. \u6559\u5b66\u76ee\u6807\uff08\u77e5\u8bc6\u4e0e\u6280\u80fd\u3001\u8fc7\u7a0b\u4e0e\u65b9\u6cd5\u3001"
        "\u60c5\u611f\u6001\u5ea6\u4e0e\u4ef7\u503c\u89c2\uff09\n"
        "2. \u6559\u5b66\u91cd\u96be\u70b9\n3. \u6559\u5b66\u65b9\u6cd5\u4e0e\u624b\u6bb5\n"
        "4. \u6559\u5b66\u8fc7\u7a0b\uff08\u5305\u542b\u65f6\u95f4\u548c\u5e08\u751f\u6d3b\u52a8\uff09\n"
        "5. \u677f\u4e66\u8bbe\u8ba1\n6. \u6559\u5b66\u53cd\u601d\u4e0e\u62d3\u5c55\u3002"
    )
    content = await complete_async(
        api_url,
        api_key,
        model,
        [{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
        timeout=60.0,
    )
    return {"content": content, "title": f"\u300a{topic}\u300b\u6559\u6848"}


def _fallback_lesson_plan(
    subject: str,
    grade: str,
    topic: str,
    duration: int,
    objectives: Optional[str],
    additional: Optional[str],
) -> dict:
    introduction = max(5, round(duration * 0.1))
    instruction = max(10, round(duration * 0.4))
    inquiry = max(10, round(duration * 0.25))
    summary = max(3, round(duration * 0.1))
    practice = max(1, duration - introduction - instruction - inquiry - summary)
    goal_text = objectives or f"\u7406\u89e3\u5e76\u638c\u63e1{topic}\u7684\u6838\u5fc3\u6982\u5ff5\u4e0e\u57fa\u672c\u539f\u7406\u3002"
    additional_text = additional or "\u7ed3\u5408\u5b66\u751f\u7684\u751f\u6d3b\u7ecf\u9a8c\u8bbe\u8ba1\u6d3b\u52a8\u3002"
    title = f"\u300a{topic}\u300b\u6559\u6848"
    content = f"""<!DOCTYPE html>
<html><head><meta charset=\"utf-8\"><style>
body {{ font-family: Arial, sans-serif; color: #303133; line-height: 1.8; }}
h1 {{ border-bottom: 2px solid #409eff; padding-bottom: 8px; }}
h2 {{ color: #409eff; margin-top: 22px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #dcdfe6; padding: 8px; vertical-align: top; }}
th {{ background: #ecf5ff; }}
</style></head><body>
<h1>{title}</h1>
<p><strong>\u5b66\u79d1\uff1a</strong>{subject} &nbsp; <strong>\u5e74\u7ea7\uff1a</strong>{grade} &nbsp; <strong>\u8bfe\u65f6\uff1a</strong>{duration}\u5206\u949f</p>
<h2>\u4e00\u3001\u6559\u5b66\u76ee\u6807</h2>
<ul><li>{goal_text}</li><li>\u80fd\u591f\u8fd0\u7528\u76f8\u5173\u77e5\u8bc6\u5206\u6790\u5b9e\u9645\u95ee\u9898\u3002</li><li>\u5728\u5408\u4f5c\u63a2\u7a76\u4e2d\u5f62\u6210\u6279\u5224\u6027\u601d\u7ef4\u3002</li></ul>
<h2>\u4e8c\u3001\u6559\u5b66\u91cd\u96be\u70b9</h2>
<p><strong>\u91cd\u70b9\uff1a</strong>{topic}\u7684\u6838\u5fc3\u6982\u5ff5\u4e0e\u5173\u952e\u65b9\u6cd5\u3002<br><strong>\u96be\u70b9\uff1a</strong>\u5c06\u77e5\u8bc6\u8fc1\u79fb\u5230\u771f\u5b9e\u60c5\u5883\u4e2d\u3002</p>
<h2>\u4e09\u3001\u6559\u5b66\u8fc7\u7a0b</h2>
<table><thead><tr><th>\u73af\u8282</th><th>\u65f6\u95f4</th><th>\u6559\u5e08\u6d3b\u52a8</th><th>\u5b66\u751f\u6d3b\u52a8</th></tr></thead><tbody>
<tr><td>\u60c5\u5883\u5bfc\u5165</td><td>{introduction}\u5206\u949f</td><td>\u521b\u8bbe\u4e0e\u4e3b\u9898\u76f8\u5173\u7684\u95ee\u9898\u60c5\u5883\u3002</td><td>\u89c2\u5bdf\u3001\u601d\u8003\u5e76\u63d0\u51fa\u7591\u95ee\u3002</td></tr>
<tr><td>\u65b0\u8bfe\u5b66\u4e60</td><td>{instruction}\u5206\u949f</td><td>\u8bb2\u89e3{topic}\u7684\u6838\u5fc3\u5185\u5bb9\u5e76\u7ec4\u7ec7\u4e92\u52a8\u3002</td><td>\u8bb0\u5f55\u8981\u70b9\u5e76\u56de\u7b54\u95ee\u9898\u3002</td></tr>
<tr><td>\u5408\u4f5c\u63a2\u7a76</td><td>{inquiry}\u5206\u949f</td><td>\u53d1\u5e03\u63a2\u7a76\u4efb\u52a1\u5e76\u8fdb\u884c\u6307\u5bfc\u3002</td><td>\u5c0f\u7ec4\u5408\u4f5c\u3001\u5206\u4eab\u6210\u679c\u3002</td></tr>
<tr><td>\u8bfe\u5802\u5c0f\u7ed3</td><td>{summary}\u5206\u949f</td><td>\u5f52\u7eb3\u5173\u952e\u77e5\u8bc6\u5e76\u53cd\u9988\u5b66\u4e60\u60c5\u51b5\u3002</td><td>\u6574\u7406\u77e5\u8bc6\u7f51\u7edc\u3002</td></tr>
<tr><td>\u8bfe\u540e\u5b9e\u8df5</td><td>{practice}\u5206\u949f</td><td>\u5e03\u7f6e\u5206\u5c42\u4efb\u52a1\u3002</td><td>\u8bb0\u5f55\u5e76\u660e\u786e\u5b8c\u6210\u8981\u6c42\u3002</td></tr>
</tbody></table>
<h2>\u56db\u3001\u6559\u5b66\u53cd\u601d\u4e0e\u62d3\u5c55</h2><p>{additional_text}</p>
</body></html>"""
    return {"content": content, "title": title}


# ── 基于项目结构化上下文的备课（计划 Task 5 验收标准 4）─────────
def generate_lesson_plan_from_project(
    db: Session,
    actor: User,
    project_id: str,
) -> dict[str, Any]:
    """读取项目结构化上下文发起 AI 备课，不由页面重复录入。

    通过 AI 治理层创建任务（scene=LESSON_PLAN），自动聚合真实问题、学科贡献、
    目标、指标、证据计划、资源、任务链与量规作为输入摘要。
    返回任务详情（含输出版本、质量问题、阻断问题数）。
    """
    job = ai_jobs_service.create_and_run_job(
        db,
        actor,
        project_id,
        AiJobScene.LESSON_PLAN,
        "教案",
    )
    detail = ai_jobs_service.get_job_detail(db, actor, job.id)
    return detail
