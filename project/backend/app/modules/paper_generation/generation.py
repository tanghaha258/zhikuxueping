import json
import uuid
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.modules.ai_gateway import complete, stream
from app.modules.paper_generation.composition import (
    compose_questions,
    parse_sections,
    pick_from_bank,
    question_to_paper_question,
)
from app.modules.paper_generation.streaming_parser import extract_question_from_buffer, find_complete_json
from app.modules.paper_generation.prompt_renderer import load_active_template, render_prompt
from app.models.enums import AiJobScene
from app.models.paper_template import PaperTemplate, AiGeneratedPaper
from app.models.ai_provider import AiProvider
from app.models.question import Question
from app.models.paper import Paper
from app.models.user import User
from app.modules.ai_jobs import service as ai_jobs_service
from app.repositories.base import BaseRepository
from app.schemas.paper_generator import EXAM_TYPE_LABELS


# ── Validation ──

def validate_template_sections(total_score: float, sections_json: Optional[str]) -> tuple[bool, str]:
    """校验 sections 中各 section total 加总是否等于 total_score。"""
    if not sections_json:
        return True, ""
    try:
        sections = json.loads(sections_json)
        if not isinstance(sections, list):
            return False, "sections 必须是 JSON 数组"
        calc_total = sum(s.get("total", 0) for s in sections)
        if abs(calc_total - total_score) > 0.01:
            return False, f"题型分值加总 ({calc_total}) 与总分 ({total_score}) 不一致"
        return True, ""
    except json.JSONDecodeError:
        return False, "sections 格式无效"


# ── D1: Template CRUD ──

def create_template(db: Session, data) -> PaperTemplate:
    valid, msg = validate_template_sections(data.total_score, data.sections)
    if not valid:
        raise ValueError(msg)
    tpl = PaperTemplate(
        name=data.name,
        exam_type=data.exam_type,
        subject=data.subject,
        grade=data.grade,
        total_score=data.total_score,
        config=data.config,
        sections=data.sections,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def list_templates(db: Session, skip: int = 0, limit: int = 100) -> list[PaperTemplate]:
    stmt = select(PaperTemplate).where(PaperTemplate.is_active == True).order_by(PaperTemplate.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_templates(db: Session) -> int:
    return db.execute(select(func.count()).select_from(PaperTemplate).where(PaperTemplate.is_active == True)).scalar() or 0


def get_template(db: Session, template_id: str) -> Optional[PaperTemplate]:
    return BaseRepository(db, PaperTemplate).get_by_id(template_id)


def update_template(db: Session, template_id: str, data) -> PaperTemplate:
    repo = BaseRepository(db, PaperTemplate)
    tpl = repo.get_by_id(template_id)
    if not tpl:
        raise ValueError("模板不存在")
    update_data = data.model_dump(exclude_unset=True)
    ts = update_data.get("total_score", tpl.total_score)
    sec = update_data.get("sections", tpl.sections)
    if "sections" in update_data or "total_score" in update_data:
        valid, msg = validate_template_sections(ts, sec)
        if not valid:
            raise ValueError(msg)
    return repo.update(tpl, update_data)


def sync_template_to_teacher(db: Session, template_id: str, teacher_id: str) -> PaperTemplate:
    """教师同步系统模板到个人，创建副本"""
    orig = get_template(db, template_id)
    if not orig:
        raise ValueError("模板不存在")
    tpl = PaperTemplate(
        name=orig.name + " (个人)",
        exam_type=orig.exam_type,
        subject=orig.subject,
        grade=orig.grade,
        total_score=orig.total_score,
        config=orig.config,
        sections=orig.sections,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


def delete_template(db: Session, template_id: str) -> bool:
    repo = BaseRepository(db, PaperTemplate)
    tpl = repo.get_by_id(template_id)
    if not tpl:
        return False
    tpl.is_active = False
    db.commit()
    return True


# ── Section defaults & Prompt builders ──

def get_default_sections(exam_type: str, subject: str) -> str:
    """按考试类型和学科推荐默认题型配置，返回 JSON string of list[SectionItem]"""
    defaults = {
        "quiz": [
            {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 10, "score_per": 4, "total": 40},
            {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 5, "score_per": 4, "total": 20},
            {"id": "sec_3", "label": "三、简答题", "type": "essay", "count": 4, "score_per": 10, "total": 40},
        ],
        "midterm": [
            {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 3, "total": 36},
            {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 6, "score_per": 4, "total": 24},
            {"id": "sec_3", "label": "三、解答题", "type": "essay", "count": 4, "score_per": 10, "total": 40},
        ],
        "final": [
            {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 15, "score_per": 2, "total": 30},
            {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 8, "score_per": 3, "total": 24},
            {"id": "sec_3", "label": "三、解答题", "type": "essay", "count": 5, "score_per": 8, "total": 40},
            {"id": "sec_4", "label": "四、附加题", "type": "essay", "count": 1, "score_per": 6, "total": 6},
        ],
    }

    subject_overrides = {
        "语文": {
            "quiz": [
                {"id": "sec_1", "label": "一、积累与运用（选择题）", "type": "choice", "count": 8, "score_per": 3, "total": 24},
                {"id": "sec_2", "label": "二、积累与运用（填空题）", "type": "fill", "count": 6, "score_per": 4, "total": 24},
                {"id": "sec_3", "label": "三、阅读理解", "type": "essay", "count": 4, "score_per": 13, "total": 52},
            ],
        },
        "英语": {
            "quiz": [
                {"id": "sec_1", "label": "一、听力理解（选择题）", "type": "choice", "count": 10, "score_per": 2, "total": 20},
                {"id": "sec_2", "label": "二、单项选择", "type": "choice", "count": 10, "score_per": 1, "total": 10},
                {"id": "sec_3", "label": "三、完形填空", "type": "fill", "count": 5, "score_per": 2, "total": 10},
                {"id": "sec_4", "label": "四、阅读与写作", "type": "essay", "count": 3, "score_per": 20, "total": 60},
            ],
        },
        "物理": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 10, "score_per": 3, "total": 30},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 5, "score_per": 4, "total": 20},
                {"id": "sec_3", "label": "三、实验探究", "type": "essay", "count": 3, "score_per": 10, "total": 30},
                {"id": "sec_4", "label": "四、计算题", "type": "essay", "count": 2, "score_per": 10, "total": 20},
            ],
        },
        "化学": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 10, "score_per": 2, "total": 20},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 5, "score_per": 4, "total": 20},
                {"id": "sec_3", "label": "三、实验探究", "type": "essay", "count": 3, "score_per": 10, "total": 30},
                {"id": "sec_4", "label": "四、计算题", "type": "essay", "count": 2, "score_per": 15, "total": 30},
            ],
        },
        "历史": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 2, "total": 24},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 6, "score_per": 3, "total": 18},
                {"id": "sec_3", "label": "三、材料分析题", "type": "essay", "count": 4, "score_per": 14.5, "total": 58},
            ],
        },
        "地理": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 2, "total": 24},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 6, "score_per": 3, "total": 18},
                {"id": "sec_3", "label": "三、综合题", "type": "essay", "count": 4, "score_per": 14.5, "total": 58},
            ],
        },
        "生物": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 2, "total": 24},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 6, "score_per": 3, "total": 18},
                {"id": "sec_3", "label": "三、探究题", "type": "essay", "count": 4, "score_per": 14.5, "total": 58},
            ],
        },
        "道德与法治": {
            "quiz": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 2, "total": 24},
                {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 4, "score_per": 3, "total": 12},
                {"id": "sec_3", "label": "三、材料分析题", "type": "essay", "count": 5, "score_per": 12.8, "total": 64},
            ],
        },
    }

    if subject in subject_overrides and exam_type in subject_overrides[subject]:
        return json.dumps(subject_overrides[subject][exam_type], ensure_ascii=False)
    return json.dumps(defaults.get(exam_type, defaults["quiz"]), ensure_ascii=False)


def build_section_prompt_block(sections_json: str) -> str:
    """从 sections JSON 构造 prompt 中的题型结构要求块"""
    sections = json.loads(sections_json) if sections_json else []
    if not sections:
        return ""
    total = sum(s.get("total", 0) for s in sections)
    lines = [f"总分为 {total} 分，严格按照以下题型分布出题，每道题的 type 字段必须使用指定值：\n"]
    for i, s in enumerate(sections, 1):
        label = s.get("label", f"题型{i}")
        count = s.get("count", 0)
        score_per = s.get("score_per", 0)
        total_s = s.get("total", 0)
        qtype = s.get("type", "")
        lines.append(f"{i}. {label}（type=\"{qtype}\"）：{count} 题，每题 {score_per} 分，共 {total_s} 分")
    lines.append("")
    return "\n".join(lines)


def count_section_total(sections_json: str) -> float:
    """计算 sections 总分"""
    if not sections_json:
        return 100.0
    try:
        sections = json.loads(sections_json)
        return sum(s.get("total", 0) for s in sections)
    except (json.JSONDecodeError, TypeError):
        return 100.0


# ── D2: AI Generation Engine ──

def _mock_generate(subject: str, grade: str, difficulty: str, knowledge_points: Optional[list[str]] = None) -> dict:
    """Mock generation — produces canned questions for testing."""
    import random
    base_questions = [
        {"index": 1, "type": "choice", "score": 5,
         "content": f"在{subject}中，以下哪个选项是正确的？",
         "options": ["A", "B", "C", "D"], "answer": "A",
         "analysis": f"这是{grade}年级{subject}的基础题。"},
        {"index": 2, "type": "fill", "score": 5,
         "content": f"请写出{subject}的一个核心概念：____",
         "answer": "核心概念", "analysis": "本题考查基础概念记忆。"},
        {"index": 3, "type": "essay", "score": 10,
         "content": f"请论述{subject}在实际生活中的应用。",
         "answer": "参考答案", "analysis": "本题考查知识应用能力。"},
    ]
    if difficulty == "hard":
        base_questions.append({
            "index": 4, "type": "choice", "score": 10,
            "content": f"综合题：关于{subject}的深层次理解",
            "options": ["A", "B", "C", "D"], "answer": "C",
            "analysis": "综合题考查知识迁移能力。",
        })
    total = sum(q["score"] for q in base_questions)
    kp = knowledge_points or []
    title = f"{grade}年级{subject}{'（' + '、'.join(kp) + '）' if kp else ''}测试"
    return {
        "title": title,
        "questions": base_questions,
        "total_score": total,
        "duration": 90,
    }


def _build_dynamic_examples(sections_json: Optional[str]) -> tuple[str, str]:
    """根据 sections 配置动态生成示例文本和 JSON 格式示例，确保与题型类型一致。"""
    type_labels = {
        "choice": "选择题", "fill": "填空题", "essay": "简答题/解答题",
        "reading": "阅读理解", "writing": "写作/作文", "judge": "判断题",
        "cloze": "完形填空", "classical": "文言文阅读", "calculate": "计算题",
        "proof": "证明题", "experiment": "实验题", "material": "材料分析题",
        "listening": "听力题",
    }
    content_by_type = {
        "choice": "以下哪个选项是正确的？",
        "fill": "请写出核心概念：____",
        "essay": "请论述相关知识在实际生活中的应用。",
        "reading": "阅读以下材料，回答问题。",
        "writing": "请根据要求完成写作。",
        "judge": "以下说法是否正确？",
        "cloze": "阅读短文，选择最佳答案填入空白处。",
        "classical": "阅读下面文言文，回答问题。",
        "calculate": "计算下列各题。",
        "proof": "证明以下结论。",
        "experiment": "设计实验验证以下假设。",
        "material": "阅读材料，分析回答问题。",
        "listening": "听录音，选择正确答案。",
    }
    if not sections_json:
        return "", ""
    try:
        sections = json.loads(sections_json)
    except (json.JSONDecodeError, TypeError):
        return "", ""
    text_lines, json_lines = [], []
    for i, sec in enumerate(sections, 1):
        sec_type = sec.get("type", "choice")
        score = sec.get("score_per", 5)
        label = type_labels.get(sec_type, sec.get("label", f"题型{i}"))
        content = content_by_type.get(sec_type, "题目内容")
        text_lines.append(f"- {label}示例：{content}")
        if sec_type == "choice":
            json_lines.append(
                f'    {{"index": {i}, "type": "{sec_type}", "score": {score}, '
                f'"content": "{content}", '
                f'"options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"], '
                f'"answer": "A", "analysis": "解析"}}'
            )
        else:
            json_lines.append(
                f'    {{"index": {i}, "type": "{sec_type}", "score": {score}, '
                f'"content": "{content}", "answer": "答案", "analysis": "解析"}}'
            )
    return "\n".join(text_lines), ",\n".join(json_lines)


def _call_ai_generate(
    db: Session,
    subject: str,
    grade: str,
    difficulty: str,
    knowledge_points: Optional[list[str]] = None,
    sections: Optional[str] = None,
    exam_type: str = "quiz",
) -> Optional[dict]:
    """调用 AI Provider 生成试卷内容"""
    try:
        provider = db.execute(
            select(AiProvider).where(AiProvider.status == "active")
        ).scalars().first()
        if not provider:
            print("AI generate: no active provider")
            return None
        kp_str = "、".join(knowledge_points or []) if knowledge_points else "无指定知识点"
        total_score = count_section_total(sections) if sections else 100.0
        exam_label = EXAM_TYPE_LABELS.get(exam_type, "单元测验")
        section_block = build_section_prompt_block(sections) if sections else ""
        example_text, example_json = _build_dynamic_examples(sections)

        prompt = f"""你是一位资深初中{subject}学科教师，现在需要为{grade}年级学生出一份{subject}学科的{exam_label}（{difficulty}难度）。

【最高优先级-绝对禁止】
你只能出{subject}学科的题目！绝对不能出任何其他学科的题目！
违反此要求将导致严重后果。

{section_block}知识点范围：{kp_str}

以下是{subject}学科的出题示例（仅参考格式，不要照抄内容）：
{example_text if example_text else "- 选择题示例：古诗词赏析、文言文理解、阅读理解、修辞手法辨析、文学常识等\n- 填空题示例：默写古诗文、填写文学常识、补全修辞手法名称等\n- 简答题示例：阅读理解分析、写作手法赏析、主题思想概括、人物形象分析等"}

请严格按以下JSON格式输出，不要包含任何其他内容（不要加markdown代码块标记）：
{{
  "title": "试卷标题（必须包含{subject}）",
  "questions": [
{example_json if example_json else '    {{"index": 1, "type": "choice", "score": 5, "content": "{subject}学科选择题内容", "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"], "answer": "A", "analysis": "解析"}},\n    {{"index": 2, "type": "fill", "score": 5, "content": "{subject}学科填空题内容____", "answer": "答案", "analysis": "解析"}},\n    {{"index": 3, "type": "essay", "score": 10, "content": "{subject}学科简答题内容", "answer": "参考答案", "analysis": "解析"}}'}
  ],
  "total_score": {total_score},
  "duration": 90
}}

要求：
1. 所有题目必须与{subject}学科直接相关
2. 每道题的 type 字段必须严格使用上方题型分布中 type="" 内指定的值，不得使用其他值
3. 严格按照上述题型分布中的题数和分数出题，不得增减
4. 各题目不得重复或高度相似
5. 选择题必须包含 4 个选项(A/B/C/D)及正确答案
6. 所有内容用中文"""
        content = complete(
            provider.api_url,
            provider.api_key,
            provider.model,
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=16384,
            timeout=180.0,
        )
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        print(f"AI generate error: {e}")
        return None


def _count_questions_by_type(questions: list) -> dict:
    """统计 AI 返回的题目中各 type 的数量"""
    counts: dict[str, int] = {}
    for q in questions:
        t = q.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def _validate_sections_match(sections_json: str, questions: list) -> tuple[bool, list[str]]:
    """校验 AI 返回的题目是否匹配 sections 配置，返回 (是否匹配, 差异描述列表)"""
    errors = []
    if not sections_json:
        return True, errors
    try:
        sections = json.loads(sections_json)
    except json.JSONDecodeError:
        return True, errors
    actual_counts = _count_questions_by_type(questions)
    for sec in sections:
        sec_type = sec.get("type", "")
        expected = sec.get("count", 0)
        actual = actual_counts.get(sec_type, 0)
        if actual != expected:
            errors.append(f"{sec.get('label', sec_type)}：期望 {expected} 题，实际 {actual} 题")
    return len(errors) == 0, errors


def generate_paper(
    db: Session,
    teacher_id: str,
    subject: str,
    grade: str,
    difficulty: str = "medium",
    template_id: Optional[str] = None,
    title: Optional[str] = None,
    knowledge_points: Optional[list[str]] = None,
    sections: Optional[str] = None,
    exam_type: str = "quiz",
) -> tuple[AiGeneratedPaper, Optional[str]]:
    # Step 1: Resolve sections (frontend > template > default)
    resolved_sections = sections
    if not resolved_sections and template_id:
        tpl = get_template(db, template_id)
        if tpl and tpl.sections:
            resolved_sections = tpl.sections
    if not resolved_sections:
        resolved_sections = get_default_sections(exam_type, subject)

    total_score = count_section_total(resolved_sections)

    # Step 2: Try AI with retry logic
    warning = None
    best_result = None
    max_retries = 2
    for attempt in range(max_retries + 1):
        ai_result = _call_ai_generate(
            db, subject, grade, difficulty, knowledge_points,
            sections=resolved_sections, exam_type=exam_type,
        )
        if not ai_result:
            continue

        questions = ai_result.get("questions", [])
        match, errors = _validate_sections_match(resolved_sections, questions)

        if match:
            best_result = ai_result
            warning = None
            break
        else:
            if attempt < max_retries:
                print(f"AI generate section mismatch (attempt {attempt+1}): {errors}")
            best_result = ai_result
            warning = f"题数不完全匹配：{'；'.join(errors)}。请检查并调整。"

    # Step 3: Fallback to mock if no valid result from AI
    result = best_result or _mock_generate(subject, grade, difficulty, knowledge_points)
    if not best_result and warning is None and result:
        warning = "AI 生成不可用，已使用模拟数据"

    paper = AiGeneratedPaper(
        teacher_id=teacher_id,
        template_id=template_id,
        subject=subject,
        grade=grade,
        title=title or result["title"],
        difficulty=difficulty,
        knowledge_points=json.dumps(knowledge_points or [], ensure_ascii=False),
        questions=json.dumps(result["questions"], ensure_ascii=False),
        total_score=total_score,
        duration=result.get("duration", 90),
        status="draft",
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper, warning


# ── Generated Paper CRUD ──

def list_generated_papers(db: Session, teacher_id: str, skip: int = 0, limit: int = 100) -> list[AiGeneratedPaper]:
    stmt = select(AiGeneratedPaper).where(
        AiGeneratedPaper.teacher_id == teacher_id
    ).order_by(AiGeneratedPaper.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_generated_papers(db: Session, teacher_id: str) -> int:
    return db.execute(
        select(func.count()).select_from(AiGeneratedPaper).where(AiGeneratedPaper.teacher_id == teacher_id)
    ).scalar() or 0


def get_generated_paper(db: Session, paper_id: str) -> Optional[AiGeneratedPaper]:
    return BaseRepository(db, AiGeneratedPaper).get_by_id(paper_id)


def update_generated_paper(db: Session, paper_id: str, data) -> AiGeneratedPaper:
    repo = BaseRepository(db, AiGeneratedPaper)
    paper = repo.get_by_id(paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    return repo.update(paper, data.model_dump(exclude_unset=True))


def finalize_paper(db: Session, paper_id: str) -> AiGeneratedPaper:
    repo = BaseRepository(db, AiGeneratedPaper)
    paper = repo.get_by_id(paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    paper.status = "finalized"

    existing = db.execute(
        select(Paper).where(Paper.title == paper.title, Paper.teacher_id == paper.teacher_id)
    ).scalars().first()
    if not existing:
        paper_record = Paper(
            title=paper.title,
            teacher_id=paper.teacher_id,
            status="draft",
        )
        db.add(paper_record)

    db.commit()
    db.refresh(paper)
    return paper


def delete_generated_paper(db: Session, paper_id: str) -> bool:
    repo = BaseRepository(db, AiGeneratedPaper)
    if not repo.get_by_id(paper_id):
        return False
    return repo.delete(paper_id)


# ── D4: Smart Compose (bank + AI hybrid) ──

def _pick_from_bank(
    db: Session,
    subject: str,
    grade: str,
    question_type: str,
    difficulty: str,
    knowledge_points: Optional[list[str]] = None,
    count: int = 5,
) -> list[Question]:
    """从题库中随机选取指定数量的题目"""
    from sqlalchemy import func
    q = select(Question).where(
        Question.subject == subject,
        Question.grade == grade,
        Question.question_type == question_type,
        Question.status == "published",
    )
    if difficulty == "easy":
        q = q.where(Question.difficulty <= 2)
    elif difficulty == "hard":
        q = q.where(Question.difficulty >= 4)
    else:
        q = q.where(Question.difficulty.between(2, 4))
    if knowledge_points:
        import json
        kp_json = json.dumps(knowledge_points, ensure_ascii=False)
        q = q.where(Question.knowledge_points.contains(kp_json[1:-1]))
    q = q.order_by(func.random()).limit(count)
    return list(db.execute(q).scalars().all())


def _estimate_total_questions(sections_json: Optional[str]) -> int:
    """从 sections 配置估算总题数"""
    if not sections_json:
        return 10
    try:
        sections = json.loads(sections_json)
        return sum(s.get("count", 0) for s in sections)
    except (json.JSONDecodeError, TypeError):
        return 10


def smart_compose_paper(
    db: Session,
    teacher_id: str,
    subject: str,
    grade: str,
    difficulty: str = "medium",
    template_id: Optional[str] = None,
    knowledge_points: Optional[list[str]] = None,
    sections: Optional[str] = None,
    total_score: float = 100.0,
    bank_ratio: float = 0.5,
    exam_type: str = "quiz",
    question_visibility=None,
) -> tuple[AiGeneratedPaper, Optional[str]]:
    resolved_sections = sections
    if not resolved_sections and template_id:
        tpl = get_template(db, template_id)
        if tpl and tpl.sections:
            resolved_sections = tpl.sections
    if not resolved_sections:
        resolved_sections = get_default_sections(exam_type, subject)

    warnings = []
    parsed_sections = parse_sections(resolved_sections)
    ai_count = sum(
        section.get("count", 0) - max(0, int(section.get("count", 0) * bank_ratio))
        for section in parsed_sections
    )

    bank_questions_by_section: list[list[dict]] = []
    for sec in parsed_sections:
        qtype = sec.get("type", "choice")
        sec_count = sec.get("count", 0)
        bank_need = max(0, int(sec_count * bank_ratio))
        bank_questions_by_section.append([])
        if bank_need > 0:
            picked = pick_from_bank(
                db, subject, grade, qtype, difficulty,
                knowledge_points, bank_need,
                visibility_filter=question_visibility,
            )
            bank_questions_by_section[-1] = [
                question_to_paper_question(q, qtype, sec.get("score_per", 5))
                for q in picked
            ]
            if len(picked) < bank_need:
                warnings.append(f"{sec.get('label', qtype)}：题库仅匹配到 {len(picked)}/{bank_need} 题")

    if ai_count > 0:
        ai_result = _call_ai_generate(
            db, subject, grade, difficulty, knowledge_points,
            sections=resolved_sections, exam_type=exam_type,
        )
        if ai_result:
            ai_questions = ai_result.get("questions", [])
            for q in ai_questions:
                q["_from_bank"] = False
        else:
            ai_questions = []
            warnings.append("AI 生成不可用，已仅使用题库题目")
        if len(ai_questions) < ai_count:
            warnings.append(f"AI 仅生成 {len(ai_questions)}/{ai_count} 题")
    else:
        ai_questions = []

    final_questions = compose_questions(
        parsed_sections,
        bank_ratio=bank_ratio,
        bank_questions_by_section=bank_questions_by_section,
        ai_questions=ai_questions,
    )

    kp_title = "、".join(knowledge_points or [])
    title = f"{grade}年级{subject}综合测试{'（' + kp_title + '）' if kp_title else ''}（智能组卷）"

    paper = AiGeneratedPaper(
        teacher_id=teacher_id,
        template_id=template_id,
        subject=subject,
        grade=grade,
        difficulty=difficulty,
        knowledge_points=json.dumps(knowledge_points or [], ensure_ascii=False),
        questions=json.dumps(final_questions, ensure_ascii=False),
        total_score=total_score,
        duration=90,
        status="draft",
        title=title,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    warning_msg = "；".join(warnings) if warnings else None
    return paper, warning_msg


# ── Streaming ──

import re as _re_module


def _extract_question_from_buf(buf: str, n: int) -> dict | None:
    """从部分 JSON 缓冲区中提取第 n 道题（0-indexed）。
    使用括号匹配 + 字符串跳过，逐题检测。
    """
    m = _re_module.search(r'"questions"\s*:\s*\[', buf)
    if not m:
        return None
    pos = m.end()
    depth = 0
    obj_start = -1
    count = -1
    while pos < len(buf):
        c = buf[pos]
        if c == '{':
            if depth == 0:
                count += 1
                obj_start = pos
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and obj_start >= 0:
                if count == n:
                    raw = buf[obj_start:pos + 1]
                    try:
                        return json.loads(raw)
                    except json.JSONDecodeError:
                        return _parse_question_lenient(raw)
                obj_start = -1
        elif c == '"':
            pos += 1
            while pos < len(buf):
                if buf[pos] == '\\':
                    pos += 2
                    continue
                if buf[pos] == '"':
                    break
                pos += 1
        pos += 1
    return None


def _parse_question_lenient(raw: str) -> dict | None:
    """当标准 JSON 解析失败时，用正则逐个提取关键字段。"""
    try:
        q: dict = {}
        for key in ("index", "type", "score", "content", "options", "answer", "analysis"):
            pat = r'"' + key + r'"\s*:\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\]|-?\d+(?:\.\d+)?|true|false|null)'
            fm = _re_module.search(pat, raw)
            if fm:
                val = fm.group(1)
                try:
                    q[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    q[key] = val.strip('"')
        if "index" in q and "content" in q:
            return q
        return None
    except Exception:
        return None


def _find_complete_json(buf: str) -> dict | None:
    """从缓冲区中找到最外层平衡的 JSON 对象并解析。"""
    depth = 0
    start = -1
    pos = 0
    while pos < len(buf):
        c = buf[pos]
        if c == '{':
            if start < 0:
                start = pos
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(buf[start:pos + 1])
                except json.JSONDecodeError:
                    return None
        elif c == '"':
            pos += 1
            while pos < len(buf):
                if buf[pos] == '\\':
                    pos += 2
                    continue
                if buf[pos] == '"':
                    break
                pos += 1
        pos += 1
    return None


_DEFAULT_PROMPT_TEMPLATE = """你是一位资深初中{subject}学科教师，现在需要为{grade}年级学生出一份{subject}学科的{exam_label}（{difficulty}难度）。

【最高优先级-绝对禁止】
你只能出{subject}学科的题目！绝对不能出任何其他学科的题目！
违反此要求将导致严重后果。

{section_block}知识点范围：{kp_str}

你的每道题的 type 字段必须严格使用 section 中指定的 type 值，不得使用其他值。

请严格按以下JSON格式输出，不要包含任何其他内容（不要加markdown代码块标记）：
{{
  "title": "试卷标题（必须包含{subject}）",
  "questions": [
    {{"index": 1, "type": "请填写section指定的type值", "score": 5, "content": "题目内容", "options": ["A. 选项内容", "B. 选项内容", "C. 选项内容", "D. 选项内容"], "answer": "A", "analysis": "解析"}},
    {{"index": 2, "type": "请填写section指定的type值", "score": 5, "content": "题目内容", "answer": "答案", "analysis": "解析"}},
    {{"index": 3, "type": "请填写section指定的type值", "score": 10, "content": "题目内容", "answer": "参考答案", "analysis": "解析"}}
  ],
  "total_score": {total_score},
  "duration": 90
}}

要求：
1. 所有题目必须与{subject}学科直接相关
2. 严格按照上述题型分布中的题数和分数出题，不得增减
3. 每道题的 type 字段必须使用上方题型分布中 type="" 内指定的值
4. 各题目不得重复或高度相似
5. 选择题必须包含 4 个选项(A/B/C/D)及正确答案
6. 所有内容用中文"""


def _build_prompt_with_template(
    *,
    db: "Session | None",
    subject: str,
    grade: str,
    difficulty: str,
    kp_str: str,
    exam_label: str,
    section_block: str,
    total_score: float,
    exam_type: str,
    sections_json: Optional[str] = None,
) -> str:
    """尝试从 DB 加载管理员配置的提示词模板，替换变量占位符后返回。
    找不到模板时使用内置默认模板。若提供 sections_json 则动态注入题型示例。
    """
    template_text = load_active_template(db, subject, exam_type) or _DEFAULT_PROMPT_TEMPLATE

    variables = {
        "subject": subject,
        "grade": grade,
        "difficulty": difficulty,
        "kp_str": kp_str,
        "exam_label": exam_label,
        "section_block": section_block,
        "total_score": str(total_score),
        "exam_type": exam_type,
    }

    example_json = None
    if sections_json:
        _, example_json = _build_dynamic_examples(sections_json)
    return render_prompt(template_text, variables, example_json=example_json)


async def _call_ai_generate_stream(
    subject: str,
    grade: str,
    difficulty: str,
    knowledge_points: Optional[list[str]] = None,
    sections: Optional[str] = None,
    exam_type: str = "quiz",
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    db: Optional["Session"] = None,
):
    """流式调用 AI Provider，边收 token 边解析，出一道题立即 yield 一道。
    不移 mock/降级，出错直接抛给调用方。
    """
    if not api_url or not api_key:
        raise ValueError("AI Provider 未配置")

    kp_str = "、".join(knowledge_points or []) if knowledge_points else "无指定知识点"
    exam_label = EXAM_TYPE_LABELS.get(exam_type, "单元测验")

    effective_sections = sections or get_default_sections(exam_type, subject)
    section_block = build_section_prompt_block(effective_sections)
    total_score = count_section_total(effective_sections)

    prompt = _build_prompt_with_template(
        db=db, subject=subject, grade=grade, difficulty=difficulty,
        kp_str=kp_str, exam_label=exam_label, section_block=section_block,
        total_score=total_score, exam_type=exam_type, sections_json=effective_sections,
    )

    json_buf = ""
    yielded_count = 0
    leftover = ""

    try:
        async for raw_chunk in stream(
            api_url,
            api_key,
            model or "",
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=16384,
            timeout=120.0,
        ):
            leftover += raw_chunk
            lines = leftover.split('\n')
            leftover = lines.pop() or ''
            for line in lines:
                line = line.strip()
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        sse_data = json.loads(line[6:])
                        delta = sse_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if delta:
                            json_buf += delta
                    except json.JSONDecodeError:
                        pass

            # 收完一个 chunk 后检查是否有新完成的题目
            while True:
                q = extract_question_from_buffer(json_buf, yielded_count)
                if q is None:
                    break
                yield {"type": "question", "data": q}
                yielded_count += 1
    except Exception:
        # 超时或网络错误：用已收到的部分数据继续
        pass

    # 流结束后解析完整结果（即使中途异常）
    result = find_complete_json(json_buf)
    if result:
        questions = result.get("questions", [])
        for q in questions[yielded_count:]:
            yield {"type": "question", "data": q}
            yielded_count += 1
        yield {"type": "done", "data": result}
    elif yielded_count > 0:
        yield {"type": "done", "data": {"title": "", "questions": [], "total_score": 100, "duration": 90}}
    else:
        yield {"type": "error", "message": "AI 返回内容无法解析为有效试卷"}


# ── Format ──

def format_paper(db: Session, paper_id: str, template_type: str, subject: str) -> AiGeneratedPaper:
    from app.modules.paper_generation.renderer import render_exam_paper
    paper = get_generated_paper(db, paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    questions = json.loads(paper.questions or "[]")
    kp = json.loads(paper.knowledge_points or "[]") if paper.knowledge_points else []
    html = render_exam_paper(
        title=paper.title,
        questions=questions,
        total_score=paper.total_score,
        duration=paper.duration,
        template_type=template_type,
        subject=subject or paper.subject,
        knowledge_points=kp,
    )
    paper.formatted_html = html
    paper.template_type = template_type
    db.commit()
    db.refresh(paper)
    return paper


def get_formatted_paper(db: Session, paper_id: str) -> Optional[AiGeneratedPaper]:
    paper = get_generated_paper(db, paper_id)
    if not paper or not paper.formatted_html:
        return None
    return paper


def update_formatted_paper(db: Session, paper_id: str, formatted_html: str, template_config: Optional[str] = None) -> AiGeneratedPaper:
    paper = get_generated_paper(db, paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    paper.formatted_html = formatted_html
    if template_config:
        paper.template_config = template_config
    db.commit()
    db.refresh(paper)
    return paper


# ── D5: Export ──

def export_paper(db: Session, paper_id: str, fmt: str = "html") -> str:
    paper = get_generated_paper(db, paper_id)
    if not paper:
        raise ValueError("试卷不存在")
    if fmt == "html":
        return _export_html(paper)
    raise ValueError(f"不支持的导出格式: {fmt}")


def _type_label(t: str) -> str:
    labels = {
        "choice": "选择题", "fill": "填空题", "essay": "简答题",
        "judge": "判断题", "reading": "阅读理解", "cloze": "完形填空",
        "writing": "写作", "classical": "文言文", "calculate": "计算题",
        "proof": "证明题", "experiment": "实验题", "material": "材料分析",
    }
    return labels.get(t, t)


def _render_question_html(q: dict, index: int) -> str:
    type_label = _type_label(q.get("type", ""))
    score = q.get("score", 0)
    content = q.get("content", "")
    options = q.get("options")
    answer = q.get("answer", "")
    analysis = q.get("analysis", "")

    opt_html = ""
    if options and isinstance(options, list):
        opt_html = '<div style="margin:8px 0 8px 24px;">'
        for opt in options:
            if isinstance(opt, dict):
                label = opt.get("label", "")
                opt_content = opt.get("content", "")
                opt_html += f'<div style="margin:4px 0;">{label}. {opt_content}</div>'
            elif isinstance(opt, str):
                opt_html += f'<div style="margin:4px 0;">{opt}</div>'
        opt_html += "</div>"
    elif options and isinstance(options, str):
        try:
            parsed = json.loads(options)
            opt_html = '<div style="margin:8px 0 8px 24px;">'
            for opt in parsed:
                label = opt.get("label", "")
                opt_content = opt.get("content", "")
                opt_html += f'<div style="margin:4px 0;">{label}. {opt_content}</div>'
            opt_html += "</div>"
        except (json.JSONDecodeError, TypeError):
            opt_html = f'<div style="margin:8px 0 8px 24px;">{options}</div>'

    return f"""
    <div style="margin-bottom:20px;padding:16px 20px;border:1px solid #d9d9d9;border-radius:6px;page-break-inside:avoid;">
        <div style="font-weight:600;font-size:14px;margin-bottom:10px;color:#1a1a1a;">
            {index}. [{type_label}]（{score}分）
        </div>
        <div style="font-size:14px;line-height:1.8;color:#333;">{content}</div>
        {opt_html}
    </div>"""


def _export_html(paper: AiGeneratedPaper) -> str:
    questions = json.loads(paper.questions or "[]")
    kp = paper.knowledge_points or "[]"
    try:
        kp_list = json.loads(kp)
        kp_str = "、".join(kp_list) if kp_list else ""
    except (json.JSONDecodeError, TypeError):
        kp_str = ""

    q_html = ""
    answer_html = ""
    for i, q in enumerate(questions, 1):
        q_html += _render_question_html(q, i)
        answer_html += f"""
        <div style="margin-bottom:12px;padding:10px 14px;border-left:3px solid #409eff;background:#f6f8fa;border-radius:4px;">
            <div style="font-weight:600;margin-bottom:4px;">第{i}题</div>
            <div style="margin:4px 0;"><strong>答案：</strong>{q.get('answer', '')}</div>
            <div style="margin:4px 0;"><strong>解析：</strong>{q.get('analysis', '')}</div>
        </div>"""

    kp_section = f'<p style="text-align:center;color:#666;font-size:13px;margin-top:4px;">知识点：{kp_str}</p>' if kp_str else ""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{paper.title}</title>
<style>
  @media print {{ body {{ padding:0 !important; }} }}
  body {{ font-family: 'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif; max-width:210mm; margin:0 auto; padding:20mm 15mm; color:#1a1a1a; }}
  h1 {{ font-size:22px; text-align:center; margin-bottom:4px; }}
  .paper-meta {{ text-align:center; color:#666; font-size:14px; margin-bottom:20px; }}
  hr {{ border:none; border-top:2px solid #333; margin:16px 0; }}
  .answer-section h2 {{ font-size:18px; border-bottom:2px solid #333; padding-bottom:6px; }}
</style>
</head>
<body>
<h1>{paper.title}</h1>
{kp_section}
<div class="paper-meta">
  <span>总分：<strong>{paper.total_score}</strong> 分</span>
  <span style="margin-left:20px;">时长：<strong>{paper.duration}</strong> 分钟</span>
</div>
<hr>
<div class="question-section">
  {q_html}
</div>
<hr class="answer-section">
<div class="answer-section">
  <h2>参考答案与解析</h2>
  {answer_html}
</div>
</body></html>"""


# ── 治理层接入（计划 Task 5）────────────────────────────────
def generate_paper_governed(
    db: Session,
    actor: User,
    project_id: str,
    *,
    output_type: str = "试卷",
) -> dict[str, Any]:
    """通过 AI 治理层生成试卷（计划 Task 5）。

    创建 scene=PAPER 的 AI 任务，自动聚合项目结构化上下文作为输入摘要。
    不使用 _mock_generate 伪数据：Provider 不可用/超时/结构无效均映射为 FAILED，
    不产生可采纳的虚假试卷。
    返回 AI 任务详情（含版本、质量问题、阻断问题数）。
    """
    job = ai_jobs_service.create_and_run_job(
        db,
        actor,
        project_id,
        AiJobScene.PAPER,
        output_type,
    )
    return ai_jobs_service.get_job_detail(db, actor, job.id)
