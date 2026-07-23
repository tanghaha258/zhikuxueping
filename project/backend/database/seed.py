"""
种子数据脚本

向数据库插入开发演示所需的基础数据。
在 backend 目录下执行：
    python -m database.seed
"""

import json
import uuid
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, Role
from app.models.school import Class, School
from app.models.subject import Subject
from app.models.project import Project, ProjectSubject, ProjectStatus
from app.models.task import Task, TaskAssignment, TaskType, TaskStatus
from app.models.paper_template import PaperTemplate
from app.models.knowledge_point import KnowledgePoint


def create_seed_organization(db):
    """创建演示账号所需的学校和班级。"""
    school = db.query(School).filter(School.code == "DEMO-SCHOOL").first()
    if not school:
        school = School(name="演示初中", code="DEMO-SCHOOL", region="演示区域")
        db.add(school)
        db.flush()

    cls = db.query(Class).filter(
        Class.school_id == school.id,
        Class.grade == "七年级",
        Class.name == "演示班",
    ).first()
    if not cls:
        cls = Class(school_id=school.id, grade="七年级", name="演示班")
        db.add(cls)
        db.flush()

    db.commit()
    db.refresh(school)
    db.refresh(cls)
    return school, cls


def create_seed_users(db, school_id=None, class_id=None):
    """创建预设演示账号"""
    seed_users = [
        {"username": "admin", "password": "admin123", "email": "admin@school.edu.cn",
         "display_name": "系统管理员", "role": Role.ADMIN},
        {"username": "schooladmin", "password": "123456", "email": "schooladmin@school.edu.cn",
         "display_name": "学校管理员", "role": Role.SCHOOL_ADMIN, "school_id": school_id},
        {"username": "zhanglaoshi", "password": "123456", "email": "zhang@school.edu.cn",
         "display_name": "张老师", "role": Role.TEACHER, "school_id": school_id},
        {"username": "lixiaoming", "password": "123456", "email": "lixiaoming@school.edu.cn",
         "display_name": "李晓明", "role": Role.STUDENT, "school_id": school_id, "class_id": class_id},
        {"username": "wangfang", "password": "123456", "email": "wangfang@school.edu.cn",
         "display_name": "王芳", "role": Role.STUDENT, "school_id": school_id, "class_id": class_id},
    ]
    created = 0
    for d in seed_users:
        existing = db.query(User).filter(User.username == d["username"]).first()
        if existing:
            existing.school_id = d.get("school_id")
            existing.class_id = d.get("class_id")
            print(f"  [跳过] 用户: {d['username']}")
            continue
        user = User(username=d["username"], email=d["email"],
                     hashed_password=hash_password(d["password"]),
                     display_name=d["display_name"], role=d["role"],
                     school_id=d.get("school_id"), class_id=d.get("class_id"),
                     is_active=True, is_locked=False, failed_attempts=0)
        db.add(user)
        created += 1
        print(f"  [创建] {d['username']} ({d['display_name']}, {d['role'].value})")
    db.commit()
    return created


def create_seed_subjects(db):
    """创建基础学科数据"""
    subjects = [
        ("语文", "chinese", None, 1),
        ("数学", "math", None, 2),
        ("英语", "english", None, 3),
        ("物理", "physics", None, 4),
        ("化学", "chemistry", None, 5),
        ("生物", "biology", None, 6),
        ("历史", "history", None, 7),
        ("地理", "geography", None, 8),
        ("道德与法治", "morality", None, 9),
        ("美术", "art", None, 10),
        ("音乐", "music", None, 11),
        ("体育与健康", "pe", None, 12),
        ("信息技术", "it", None, 13),
        ("劳动", "labor", None, 14),
    ]
    created = 0
    for name, code, desc, sort in subjects:
        if db.query(Subject).filter(Subject.code == code).first():
            print(f"  [跳过] 学科: {name}")
            continue
        db.add(Subject(name=name, code=code, description=desc, sort_order=sort))
        created += 1
        print(f"  [创建] 学科: {name}")
    db.commit()
    return created


def create_seed_projects_and_tasks(db):
    """创建示例项目、任务并分配给学生"""
    teacher = db.query(User).filter(User.username == "zhanglaoshi").first()
    students = db.query(User).filter(User.role == Role.STUDENT).all()
    subjects = {s.code: s for s in db.query(Subject).all()}

    if not teacher or not students:
        print("  [跳过] 示例项目: 缺少教师或学生数据")
        return 0, 0

    projects_def = [
        {
            "title": "校园垃圾分类调查报告",
            "description": "通过跨学科项目，让学生了解垃圾分类的重要性，掌握调查问卷设计、数据分析、报告撰写等综合能力。",
            "grade": "八年级", "status": ProjectStatus.ACTIVE,
            "subject_codes": ["biology", "chemistry", "morality"],
            "tasks": [
                {"title": "设计垃圾分类调查问卷", "description": "设计一份面向社区居民的垃圾分类意识调查问卷，至少包含10个问题。",
                 "task_type": TaskType.INDIVIDUAL, "max_score": 100},
                {"title": "数据采集与统计分析", "description": "回收问卷并完成数据清洗和统计分析，使用图表呈现关键发现。",
                 "task_type": TaskType.GROUP, "max_score": 100},
                {"title": "撰写调查报告", "description": "撰写完整的垃圾分类调查报告，包含背景、方法、数据分析和建议。",
                 "task_type": TaskType.INDIVIDUAL, "max_score": 100},
            ]
        },
        {
            "title": "古诗词中的地理世界",
            "description": "从古诗词中发掘地理知识，将文学与地理学科融合，培养学生的综合人文素养。",
            "grade": "七年级", "status": ProjectStatus.ACTIVE,
            "subject_codes": ["chinese", "geography"],
            "tasks": [
                {"title": "古诗词地理分布图绘制", "description": "选取10首描写不同地域的古诗词，在地图上标注其地理位置。",
                 "task_type": TaskType.INDIVIDUAL, "max_score": 100},
                {"title": "诗词中的气候与地貌分析", "description": "分析古诗词中描述的气候特征和地貌类型，撰写分析报告。",
                 "task_type": TaskType.GROUP, "max_score": 100},
            ]
        },
        {
            "title": "校园节水方案设计",
            "description": "运用数学建模方法分析校园用水数据，设计科学合理的节水方案。",
            "grade": "八年级", "status": ProjectStatus.ACTIVE,
            "subject_codes": ["math", "physics"],
            "tasks": [
                {"title": "校园用水量数据采集", "description": "收集学校各区域一周的用水量数据，建立数据记录表。",
                 "task_type": TaskType.GROUP, "max_score": 100},
                {"title": "用水模型建立与分析", "description": "基于采集数据建立用水量预测模型，识别节水潜力点。",
                 "task_type": TaskType.GROUP, "max_score": 100},
            ]
        },
    ]

    proj_count = 0
    task_count = 0
    for pd in projects_def:
        existing = db.query(Project).filter(Project.title == pd["title"]).first()
        if existing:
            print(f"  [跳过] 项目: {pd['title']}")
            continue

        project = Project(title=pd["title"], description=pd["description"],
                          grade=pd["grade"], status=pd["status"],
                          creator_id=teacher.id)
        db.add(project)
        db.flush()

        # Link subjects
        for code in pd["subject_codes"]:
            subj = subjects.get(code)
            if subj:
                db.add(ProjectSubject(project_id=project.id, subject_id=subj.id))

        # Create tasks
        for td in pd["tasks"]:
            deadline = datetime.now() + timedelta(days=14)
            task = Task(project_id=project.id, title=td["title"],
                        description=td["description"],
                        task_type=td["task_type"], max_score=td["max_score"],
                        status=TaskStatus.PENDING, created_by=teacher.id,
                        deadline=deadline)
            db.add(task)
            db.flush()

            # Assign to all students
            for stu in students:
                db.add(TaskAssignment(task_id=task.id, student_id=stu.id,
                                      assigned_at=datetime.now()))
            task_count += 1

        proj_count += 1
        print(f"  [创建] 项目: {pd['title']} ({len(pd['tasks'])} 个任务)")

    db.commit()
    return proj_count, task_count


def create_seed_paper_templates(db):
    """预置试卷模板（周测/期中/期末）
    
    每种考试类型使用标准题型配置，所有 sections 的 total 汇总 = total_score = 100。
    sections 使用含 id/label/count/score_per/total 的完整结构，
    直接写入 PaperTemplate.total_score 字段。
    """
    subjects = {s.code: s.name for s in db.query(Subject).all()}
    grades = ["7", "8", "9"]

    # 各考试类型的题型配置，所有 section total 汇总 = 100
    exam_sections_map = {
        "quiz": {
            "label": "周测",
            "duration": 30,
            "difficulty": "easy",
            "sections": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 10, "score_per": 4, "total": 40},
                {"id": "sec_2", "label": "二、填空题", "type": "fill",   "count": 5,  "score_per": 4, "total": 20},
                {"id": "sec_3", "label": "三、简答题", "type": "essay",  "count": 4,  "score_per": 10, "total": 40},
            ],
        },
        "midterm": {
            "label": "期中考试",
            "duration": 60,
            "difficulty": "medium",
            "sections": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 12, "score_per": 3, "total": 36},
                {"id": "sec_2", "label": "二、填空题", "type": "fill",   "count": 6,  "score_per": 4, "total": 24},
                {"id": "sec_3", "label": "三、解答题", "type": "essay",  "count": 4,  "score_per": 10, "total": 40},
            ],
        },
        "final": {
            "label": "期末考试",
            "duration": 90,
            "difficulty": "hard",
            "sections": [
                {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 15, "score_per": 2, "total": 30},
                {"id": "sec_2", "label": "二、填空题", "type": "fill",   "count": 8,  "score_per": 3, "total": 24},
                {"id": "sec_3", "label": "三、解答题", "type": "essay",  "count": 5,  "score_per": 8, "total": 40},
                {"id": "sec_4", "label": "四、附加题", "type": "essay",  "count": 1,  "score_per": 6, "total": 6},
            ],
        },
    }

    created = 0
    for exam_type, exam_conf in exam_sections_map.items():
        for code, name in subjects.items():
            for grade in grades:
                tpl_name = f"{name}{grade}年级{exam_conf['label']}"
                existing = db.query(PaperTemplate).filter(
                    PaperTemplate.name == tpl_name,
                    PaperTemplate.exam_type == exam_type,
                    PaperTemplate.subject == code,
                    PaperTemplate.grade == grade,
                ).first()
                if existing:
                    continue

                sections = json.dumps(exam_conf["sections"], ensure_ascii=False)
                total_score = sum(s["total"] for s in exam_conf["sections"])

                config = json.dumps({
                    "difficulty": exam_conf["difficulty"],
                    "duration": exam_conf["duration"],
                    "total_score": total_score,
                }, ensure_ascii=False)

                db.add(PaperTemplate(
                    name=tpl_name, exam_type=exam_type,
                    subject=code, grade=grade,
                    total_score=total_score,
                    config=config, sections=sections,
                ))
                created += 1
    db.commit()
    return created


def create_seed_knowledge_points(db):
    """预置常用知识点"""
    kp_data = {
        "chinese": {
            "7": ["字音字形", "词语理解", "修辞手法", "文言文阅读", "现代文阅读", "记叙文写作", "古诗词鉴赏"],
            "8": ["议论文阅读", "说明文阅读", "文言文实词", "文言文虚词", "作文立意", "材料作文"],
            "9": ["中考综合复习", "文言文翻译", "文学常识", "名著阅读", "议论文写作", "语言综合运用"],
        },
        "math": {
            "7": ["有理数", "整式加减", "一元一次方程", "二元一次方程组", "不等式", "几何图形", "数据的收集与整理"],
            "8": ["三角形", "全等三角形", "轴对称", "整式乘除", "分式", "二次根式", "勾股定理"],
            "9": ["一元二次方程", "二次函数", "圆", "相似三角形", "锐角三角函数", "概率初步"],
        },
        "english": {
            "7": ["一般现在时", "现在进行时", "人称代词", "名词复数", "基数词序数词", "There be 句型"],
            "8": ["一般过去时", "现在完成时", "被动语态", "比较级最高级", "宾语从句", "条件状语从句"],
            "9": ["定语从句", "过去完成时", "虚拟语气", "主谓一致", "非谓语动词", "中考语法综合"],
        },
        "physics": {
            "8": ["机械运动", "声现象", "物态变化", "光现象", "透镜", "质量与密度"],
            "9": ["力与运动", "压强", "浮力", "功与机械", "内能", "欧姆定律", "电功率"],
        },
        "chemistry": {
            "9": ["物质的变化", "空气", "氧气", "水", "化学方程式", "碳和碳的氧化物", "金属材料", "溶液"],
        },
        "biology": {
            "7": ["生物与环境", "细胞", "植物", "人体生理"],
            "8": ["动物的运动", "遗传与变异", "进化", "生态系统"],
        },
        "history": {
            "7": ["史前时期", "夏商周", "秦汉", "三国两晋南北朝"],
            "8": ["隋唐", "宋元", "明清", "近代化探索"],
            "9": ["世界古代史", "世界近代史", "世界现代史"],
        },
        "geography": {
            "7": ["地球与地图", "世界地理", "居民与聚落"],
            "8": ["中国地理", "区域地理", "自然资源"],
        },
        "morality": {
            "7": ["青春时光", "情绪情感", "集体生活"],
            "8": ["权利义务", "社会责任", "国家制度"],
            "9": ["和谐与梦想", "世界舞台", "法治教育"],
        },
    }
    from app.models.knowledge_point import KnowledgePoint
    created = 0
    subjects = {s.code: s for s in db.query(Subject).all()}
    for code, grades in kp_data.items():
        subject = subjects.get(code)
        if not subject:
            continue
        for grade, points in grades.items():
            for name in points:
                existing = db.query(KnowledgePoint).filter(
                    KnowledgePoint.subject == code,
                    KnowledgePoint.grade == grade,
                    KnowledgePoint.name == name,
                ).first()
                if existing:
                    continue
                db.add(KnowledgePoint(subject=code, grade=grade, name=name))
                created += 1
    db.commit()
    return created


def _get_default_prompt(subject: str, exam_type: str) -> str:
    """生成指定学科+考试类型的默认提示词模板字符串"""
    exam_label = {"quiz": "周测", "midterm": "期中考试", "final": "期末考试"}.get(exam_type, "测试")

    return f"""你是一位资深初中{subject}学科教师，现在需要为{{grade}}年级学生出一份{subject}学科的{exam_label}（{{difficulty}}难度）。

【最高优先级-绝对禁止】
你只能出{subject}学科的题目！绝对不能出任何其他学科的题目！

{{section_block}}知识点范围：{{kp_str}}

你的每道题的 type 字段必须严格使用 section 中指定的 type 值，不得使用其他值。

请严格按以下JSON格式输出，不要包含任何其他内容：
{{
  "title": "试卷标题（必须包含{subject}）",
  "questions": [
    {{{{""index"": 1, ""type"": ""请填写section指定的type值"", ""score"": 5, ""content"": ""题目内容"", ""options"": [""A. 选项内容"", ""B. 选项内容"", ""C. 选项内容"", ""D. 选项内容""], ""answer"": ""A"", ""analysis"": ""解析""}}}},
    {{{{""index"": 2, ""type"": ""请填写section指定的type值"", ""score"": 5, ""content"": ""题目内容"", ""answer"": ""答案"", ""analysis"": ""解析""}}}},
    {{{{""index"": 3, ""type"": ""请填写section指定的type值"", ""score"": 10, ""content"": ""题目内容"", ""answer"": ""参考答案"", ""analysis"": ""解析""}}}}
  ],
  ""total_score"": {{total_score}},
  ""duration"": 90
}}

要求：
1. 所有题目必须与{subject}学科直接相关
2. 严格按照上述题型分布中的题数和分数出题，不得增减
3. 每道题的 type 字段必须使用上方题型分布中 type="" 内指定的值
4. 各题目不得重复或高度相似
5. 选择题必须包含 4 个选项(A/B/C/D)及正确答案
6. 所有内容用中文"""


def seed_prompt_templates(db):
    """表为空时插入 9×3=27 条默认提示词模板"""
    from app.models.prompt_template import PromptTemplate
    from sqlalchemy import func, select

    count = db.scalar(select(func.count()).select_from(PromptTemplate))
    if count > 0:
        print("  [跳过] 提示词模板: 已有记录，保留管理员修改")
        return 0

    subjects = ["语文","数学","英语","物理","化学","历史","地理","生物","道德与法治"]
    exam_types = [("quiz","周测"), ("midterm","期中考试"), ("final","期末考试")]

    created = 0
    for subject in subjects:
        for exam_type, exam_label in exam_types:
            template = PromptTemplate(
                id=str(uuid.uuid4()),
                name=f"{subject}{exam_label}标准模板",
                subject=subject,
                exam_type=exam_type,
                template=_get_default_prompt(subject, exam_type),
                description=f"{subject}学科{exam_label}默认提示词模板（首次初始化生成，管理员可编辑）",
                is_active=True,
            )
            db.add(template)
            created += 1
            print(f"  [创建] 模板: {template.name}")
    db.commit()
    print(f"  [完成] 共创建 {created} 条提示词模板")
    return created


def main():
    print("=" * 55)
    print("  初中跨学科教学评一体化平台 - 种子数据")
    print("=" * 55)

    db = SessionLocal()
    try:
        school, cls = create_seed_organization(db)
        created_users = create_seed_users(db, school.id, cls.id)
        created_subjects = create_seed_subjects(db)
        proj_count, task_count = create_seed_projects_and_tasks(db)
        created_templates = create_seed_paper_templates(db)
        created_kp = create_seed_knowledge_points(db)
        created_prompts = seed_prompt_templates(db)

        print("-" * 55)
        print(f"  完成！")
        print(f"  用户: 新增 {created_users}，跳过 {5 - created_users}")
        print(f"  学科: 新增 {created_subjects}，跳过 {14 - created_subjects}")
        if proj_count:
            print(f"  项目: 新增 {proj_count}，任务: 新增 {task_count}")
        else:
            print(f"  项目: 已存在，跳过")
        if created_templates:
            print(f"  试卷模板: 新增 {created_templates}")
        if created_kp:
            print(f"  知识点: 新增 {created_kp}")
        if created_prompts:
            print(f"  提示词模板: 新增 {created_prompts}")
    finally:
        db.close()

    print("=" * 55)
    print("  预设账号：")
    print("    admin       / admin123  (系统管理员)")
    print("    schooladmin / 123456    (学校管理员)")
    print("    zhanglaoshi / 123456    (教师)")
    print("    lixiaoming  / 123456    (学生)")
    print("    wangfang    / 123456    (学生)")
    print("=" * 55)


if __name__ == "__main__":
    main()
