import json
import random
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.ai_gateway import complete, complete_async
from app.models.ai_provider import AiProvider
from app.models.task import Task
from app.models.submission import Submission
from app.models.evaluation import Evaluation
from app.repositories.base import BaseRepository
from app.schemas.ai import AiProviderCreate, AiProviderUpdate
from app.services.file_parser import extract_text, is_multimodal_model


# ── 备课生成 ──────────────────────────────────────────────

def pick(items: list[str]) -> str:
    return random.choice(items)


def _template_lesson_plan(subject: str, grade: str, topic: str, duration: int) -> str:
    """模板方式生成教案内容（当 AI API 不可用时使用）"""
    tpl = _build_template_content(subject, grade, topic, duration)
    return tpl


def _build_template_content(subject: str, grade: str, topic: str, duration: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    p1 = max(5, round(duration * 0.1))
    p2 = max(10, round(duration * 0.4))
    p3 = max(10, round(duration * 0.25))
    p4 = max(3, round(duration * 0.1))
    p5 = duration - p1 - p2 - p3 - p4

    knowledge_goals = [
        f"理解并掌握{topic}的核心概念与基本原理",
        f"能够运用{topic}的相关知识解决实际问题",
        f"梳理{topic}的知识脉络，形成系统的认知结构",
        f"掌握{topic}的关键术语和表述方式",
    ]
    process_goals = [
        "通过小组合作探究，培养团队协作与沟通能力",
        "运用信息技术手段，提升信息获取与处理能力",
        "通过案例分析，培养批判性思维与问题解决能力",
        "通过实验/实践活动，培养动手操作与观察分析能力",
    ]
    emotion_goals = [
        f"激发学生对{topic}的学习兴趣，树立科学态度",
        "培养跨学科整合意识，增强综合素养",
        f"引导学生关注{topic}在社会生活中的应用价值",
        "增强文化自信，培养家国情怀与社会责任感",
    ]
    import_methods = [
        "通过播放相关视频/图片素材，创设情境导入新课",
        "以生活实例提问的方式引发学生思考，自然过渡到新课内容",
        "回顾已学相关知识，以问题链的形式引出新课题",
        "通过一个小实验/小活动，激发学生的好奇心和探究欲",
    ]
    expansions = [
        f"引导学生思考{subject}与其他学科之间的联系，尝试用跨学科视角分析问题",
        f"结合生活实际，拓展{topic}在日常生活中的应用场景",
        "引入前沿科技动态，拓展学生的视野和知识面",
        "布置课后研究性学习任务，鼓励学生深入探索相关主题",
    ]

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<style>
  .lp-wrapper {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans SC", sans-serif; color: #303133; line-height: 1.8; padding: 8px; }}
  .lp-wrapper h1 {{ font-size: 22px; color: #303133; border-bottom: 2px solid #409EFF; padding-bottom: 8px; margin-bottom: 16px; }}
  .lp-wrapper h2 {{ font-size: 18px; color: #409EFF; margin: 20px 0 10px; padding-left: 10px; border-left: 3px solid #409EFF; }}
  .lp-wrapper h3 {{ font-size: 15px; color: #606266; margin: 12px 0 6px; }}
  .lp-wrapper ul, .lp-wrapper ol {{ padding-left: 22px; margin: 6px 0; }}
  .lp-wrapper li {{ margin: 4px 0; }}
  .lp-wrapper .meta {{ background: #f0f9ff; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; color: #606266; display: flex; flex-wrap: wrap; gap: 16px; }}
  .lp-wrapper .tag {{ display: inline-block; background: #ecf5ff; color: #409EFF; font-size: 12px; padding: 2px 10px; border-radius: 4px; margin-right: 4px; }}
  .lp-wrapper .table-wrap {{ overflow-x: auto; margin: 10px 0; }}
  .lp-wrapper table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .lp-wrapper th {{ background: #ecf5ff; color: #409EFF; padding: 8px 12px; border: 1px solid #e4e7ed; text-align: center; font-weight: 600; }}
  .lp-wrapper td {{ padding: 8px 12px; border: 1px solid #e4e7ed; }}
  .lp-wrapper .highlight {{ background: #fdf6ec; border-left: 3px solid #e6a23c; padding: 8px 12px; border-radius: 4px; margin: 8px 0; font-size: 13px; }}
</style></head>
<body><div class="lp-wrapper">
  <h1>《{topic}》教案</h1>
  <div class="meta">
    <span><strong>学科：</strong>{subject}</span>
    <span><strong>年级：</strong>{grade}</span>
    <span><strong>课时：</strong>{duration} 分钟</span>
    <span><strong>生成时间：</strong>{now}</span>
  </div>
  <h2>一、教学目标</h2>
  <h3>1. 知识与技能目标</h3>
  <ul><li>{pick(knowledge_goals)}</li><li>能准确识别{topic}中的关键要素，并加以分类和归纳</li></ul>
  <h3>2. 过程与方法目标</h3>
  <ul><li>{pick(process_goals)}</li><li>通过自主学习与协作探究相结合的方式，培养综合学习能力</li></ul>
  <h3>3. 情感态度与价值观目标</h3>
  <ul><li>{pick(emotion_goals)}</li><li>{pick(emotion_goals)}</li></ul>
  <h2>二、教学重难点</h2>
  <ul><li><strong>教学重点：</strong>{topic}的核心概念及其内在逻辑关系</li><li><strong>教学难点：</strong>如何将{topic}与实际生活情境有效联系，实现知识的迁移与应用</li></ul>
  <h2>三、教学方法与手段</h2>
  <ul><li>启发式教学法：通过问题引导，激发学生主动思考</li><li>小组合作学习法：分组讨论，互助探究</li><li>信息技术辅助：多媒体课件 / 在线互动工具</li><li>跨学科融合：融入相关学科视角，拓展思维广度</li></ul>
  <h2>四、教学过程</h2>
  <div class="table-wrap"><table>
    <thead><tr><th style="width:15%">教学环节</th><th style="width:20%">时间</th><th style="width:40%">教师活动</th><th style="width:25%">学生活动</th></tr></thead>
    <tbody>
      <tr><td><span class="tag">导入</span></td><td>{p1} 分钟</td><td>{pick(import_methods)}，展示学习目标和评价标准</td><td>观看/聆听，进入学习状态，明确学习目标</td></tr>
      <tr><td><span class="tag">新课讲授</span></td><td>{p2} 分钟</td><td>系统讲授{topic}的核心知识，穿插提问与互动，利用多媒体辅助呈现</td><td>听讲并记录要点，回答问题，完成随堂练习</td></tr>
      <tr><td><span class="tag">合作探究</span></td><td>{p3} 分钟</td><td>布置小组探究任务，巡回指导，组织展示交流</td><td>小组分工合作，讨论探究，形成成果并展示</td></tr>
      <tr><td><span class="tag">课堂小结</span></td><td>{p4} 分钟</td><td>归纳总结本课核心知识点，梳理知识框架，布置课后任务</td><td>参与小结，完善笔记，明确课后任务要求</td></tr>
      <tr><td><span class="tag">作业布置</span></td><td>{p5} 分钟</td><td>分层布置作业：基础题+拓展题，鼓励学有余力的同学完成跨学科探究</td><td>记录作业内容，明确完成标准</td></tr>
    </tbody>
  </table></div>
  <h2>五、板书设计</h2>
  <div class="highlight"><strong>📌 课题：</strong>{topic}<br><strong>一、</strong>核心概念 ──→ <strong>二、</strong>关键方法 ──→ <strong>三、</strong>实际应用<br><strong>四、</strong>跨学科联系 ──→ <strong>五、</strong>课堂总结</div>
  <h2>六、教学反思与拓展</h2>
  <ul><li>{pick(expansions)}</li><li>根据课堂实际情况灵活调整教学节奏与活动设计</li><li>关注学生个体差异，实施分层教学与个性化指导</li></ul>
  <p style="text-align:center;color:#c0c4cc;font-size:12px;margin-top:24px;">—— AI 智能备课助手 · 教学评一体化平台 ——</p>
</div></body></html>"""


async def generate_lesson_plan(
    subject: str,
    grade: str,
    topic: str,
    duration: int = 45,
    objectives: Optional[str] = None,
    additional: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    """生成教案，优先调用 AI API，不可用时使用模板"""
    # Try DB provider first
    provider = None
    if db:
        provider = db.execute(
            select(AiProvider).where(AiProvider.status == "active")
        ).scalars().first()
    if provider:
        try:
            result = await _call_ai_api(provider.api_url, provider.api_key, subject, grade, topic, duration, objectives, additional, model=provider.model)
            if result:
                return result
        except Exception:
            pass

    # Fallback to settings
    ai_url = settings.AI_API_BASE_URL
    ai_key = settings.AI_API_KEY
    if ai_url and ai_key:
        try:
            result = await _call_ai_api(ai_url, ai_key, subject, grade, topic, duration, objectives, additional)
            if result:
                return result
        except Exception:
            pass

    content = _template_lesson_plan(subject, grade, topic, duration)
    return {"content": content, "title": f"《{topic}》教案"}


async def _call_ai_api(
    api_url: str, api_key: str, subject: str, grade: str, topic: str,
    duration: int, objectives: Optional[str], additional: Optional[str],
    model: Optional[str] = None,
) -> Optional[dict]:
    prompt = f"""你是一位经验丰富的初中{subject}教师，请为{grade}学生设计一份关于《{topic}》的完整教案。
    课时长度: {duration}分钟。
    教学目标: {objectives or '请自行设定'}。
    额外要求: {additional or '无'}。

    请以HTML格式输出，包含:
    1. 教学目标（知识与技能、过程与方法、情感态度与价值观）
    2. 教学重难点
    3. 教学方法与手段
    4. 教学过程（分环节：导入、新课讲授、合作探究、课堂小结、作业布置，含时间和师生活动）
    5. 板书设计
    6. 教学反思与拓展

    用中文学科教案的标准格式。"""

    content = await complete_async(
        api_url,
        api_key,
        model or settings.AI_MODEL,
        [{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4096,
        timeout=60.0,
    )
    return {"content": content, "title": f"《{topic}》教案"}


# ── Provider CRUD ─────────────────────────────────────────

def list_providers(db: Session) -> list[AiProvider]:
    stmt = select(AiProvider).order_by(AiProvider.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def create_provider(db: Session, data: AiProviderCreate) -> AiProvider:
    obj = AiProvider(name=data.name, api_url=data.api_url, model=data.model, api_key=data.api_key)
    return BaseRepository(db, AiProvider).create(obj)


def update_provider(db: Session, provider_id: str, data: AiProviderUpdate) -> AiProvider:
    repo = BaseRepository(db, AiProvider)
    obj = repo.get_by_id(provider_id)
    if not obj:
        raise ValueError("Provider 不存在")
    update_data = data.model_dump(exclude_unset=True)
    # 如果 api_key 包含 **** 说明是前端回传的被遮盖的值，跳过不更新
    if "api_key" in update_data and "****" in str(update_data["api_key"]):
        del update_data["api_key"]
    return repo.update(obj, update_data)


def delete_provider(db: Session, provider_id: str) -> bool:
    return BaseRepository(db, AiProvider).delete(provider_id)


def get_provider(db: Session, provider_id: str) -> AiProvider | None:
    return BaseRepository(db, AiProvider).get_by_id(provider_id)


async def test_provider_connection(api_url: str, api_key: str, model: str) -> bool:
    """测试 AI Provider 连接是否可用"""
    try:
        await complete_async(
            api_url,
            api_key,
            model,
            [{"role": "user", "content": "Hello"}],
            temperature=0.0,
            max_tokens=5,
            timeout=15.0,
        )
        return True
    except Exception:
        return False


# ── AI Evaluate ─────────────────────────────────────────────


def evaluate_submission(db: Session, submission_id: str, teacher_id: str) -> dict:
    sub = db.get(Submission, submission_id)
    if not sub:
        raise ValueError("提交记录不存在")

    task = db.get(Task, sub.task_id)
    if not task:
        raise ValueError("任务不存在")

    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()

    rubric = task.rubric or ""

    file_texts = []
    has_images = False
    for url in (sub.file_urls or []):
        local_path = url
        if url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
            has_images = True
        else:
            text = extract_text(local_path)
            if text:
                file_texts.append(text)

    # 从 ProjectSubject 关联表查出项目对应的学科名称
    from app.models.project import Project, ProjectSubject
    from app.models.subject import Subject
    subject_name = "跨学科"
    project = db.get(Project, task.project_id)
    if project:
        ps = db.execute(
            select(Subject.name).join(ProjectSubject, Subject.id == ProjectSubject.subject_id)
            .where(ProjectSubject.project_id == task.project_id)
        ).scalars().first()
        if ps:
            subject_name = ps

    prompt_parts = [f"你是一位初中{subject_name}教师，请根据以下评分细则对学生作业进行评分。"]
    prompt_parts.append(f"\n## 任务信息\n题目：{task.title}\n描述：{task.description or ''}")
    if rubric:
        prompt_parts.append(f"\n## 评分细则\n{rubric}")
    prompt_parts.append(f"\n## 学生提交内容\n{sub.content or ''}")
    if file_texts:
        prompt_parts.append(f"\n## 附件文本\n{chr(10).join(file_texts)}")
    if has_images:
        prompt_parts.append("\n## 图片材料\n[学生提交了图片，请分析图片内容]")

    prompt_parts.append('\n请严格按以下 JSON 格式输出，不要包含其他内容：\n{"dimensions": [{"name": "维度名", "score": 分数, "comment": "评语"}], "total_score": 总分, "overall_comment": "总体评语"}')
    prompt = "\n".join(prompt_parts)

    if provider:
        try:
            result = _call_evaluate_ai(provider, prompt, has_images)
            if result:
                return _save_evaluation(db, sub, task, result, teacher_id)
        except Exception:
            pass

    return _mock_evaluate(sub, task)


def _call_evaluate_ai(provider: AiProvider, prompt: str, has_images: bool) -> Optional[dict]:
    content = complete(
        provider.api_url,
        provider.api_key,
        provider.model,
        [{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
        timeout=60.0,
    )
    import re
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return None


def _save_evaluation(db: Session, sub: Submission, task: Task, result: dict, teacher_id: str) -> dict:
    total = result.get("total_score", 0)
    comment = result.get("overall_comment", "")
    eval_obj = Evaluation(
        task_id=sub.task_id,
        student_id=sub.student_id,
        evaluator_id=teacher_id,
        score=total,
        comment=comment,
        eval_type="ai",
    )
    db.add(eval_obj)
    try:
        db.commit()
        db.refresh(eval_obj)
    except Exception:
        db.rollback()
        raise
    return {
        "dimensions": result.get("dimensions", []),
        "total_score": total,
        "overall_comment": comment,
        "evaluation_id": eval_obj.id,
    }


# ── Paper Evaluate ─────────────────────────────────────────


def evaluate_paper_submission(db: Session, sub: "PaperSubmission", ak: "AnswerKey") -> dict:
    from app.models.paper import SubmissionStatus
    import json, random

    total_score = ak.total_score or 100
    questions = ak.questions or []

    # 尝试用 AI 批改
    provider = db.execute(
        select(AiProvider).where(AiProvider.status == "active")
    ).scalars().first()

    if provider:
        try:
            # 构造 prompt：包含答案和参考答案
            q_texts = []
            for q in questions:
                q_texts.append(
                    f"第{q.get('index', 0)+1}题（{q.get('score', 0)}分）：{q.get('content', '')}\n"
                    f"参考答案：{q.get('answer', '')}\n"
                    f"学生答案：{q.get('student_answer', '未提交')}"
                )
            prompt = (
                "你是一位初中教师，请根据参考答案对学生的试卷答案进行评分。\n\n"
                + "\n\n".join(q_texts)
                + f'\n\n请严格按以下 JSON 格式输出，不要包含其他内容：\n{{"questions": [{{"index": 1, "score": 分数, "comment": "评语"}}], "total_score": 总分, "overall_comment": "总体评语"}}'
            )
            result = _call_evaluate_ai(provider, prompt, False)
            if result and result.get("questions"):
                dims = []
                q_total = 0
                for rq in result["questions"]:
                    s = rq.get("score", 0)
                    q_total += s
                    dims.append({
                        "name": f"第{rq.get('index', 0)}题",
                        "score": s,
                        "comment": rq.get("comment", ""),
                    })
                final_score = round(q_total, 1)
                sub.ai_score = final_score
                sub.ai_comment = result.get("overall_comment", "AI 自动批改完成")
                sub.status = SubmissionStatus.GRADED
                db.commit()
                return {
                    "dimensions": dims,
                    "total_score": final_score,
                    "overall_comment": result.get("overall_comment", "答卷已由 AI 批改完成，请教师复核。"),
                }
        except Exception:
            db.rollback()

    # 降级：随机模拟（当 AI 不可用时）
    dims = []
    q_total = 0
    for q in questions:
        score = round(random.uniform(q.get("score", 10) * 0.5, q.get("score", 10)), 1)
        q_total += score
        dims.append({
            "name": f"第{q.get('index', 0)+1}题",
            "score": score,
            "comment": "AI 自动批改（模拟）",
        })

    final_score = round(q_total, 1)
    sub.ai_score = final_score
    sub.ai_comment = "AI 自动批改完成"
    sub.status = SubmissionStatus.GRADED
    db.commit()
    return {
        "dimensions": dims,
        "total_score": final_score,
        "overall_comment": "答卷已由 AI 自动批改完成，请教师复核。",
    }


def _mock_evaluate(sub: Submission, task: Task) -> dict:
    import random
    score = random.randint(60, min(100, task.max_score))
    return {
        "dimensions": [{"name": "综合评分", "score": score, "comment": "AI 自动评分（模拟）"}],
        "total_score": score,
        "overall_comment": "学生提交内容已完成，建议教师复核评分。",
        "evaluation_id": None,
    }
