"""跨学科 AI 内容质量规则测试（计划 Task 5 验收标准 2）。

覆盖五条规则：
- subject_mismatch：AI 输出未体现核心学科（学科拼盘）
- unused_contribution：支撑学科贡献未转化为任务或资源
- missing_stage：课前/课中/课后三阶段任务链不完整
- missing_resource_tier：基础/提升/拓展三级资源不全
- missing_evaluation：缺少量规或评价指标

规则分两级：
- 项目级规则（validate_project_context）：在任务创建时执行
- 版本级规则（validate_output）：在 AI 输出后执行

全部使用假 Provider（monkeypatch _call_provider），不调用真实模型。
"""
from __future__ import annotations

import uuid

from app.models.ai_provider import AiProvider
from app.models.enums import (
    AiJobScene,
    QualityRuleCode,
    QualitySeverity,
    ResourceTier,
    TeachingStage,
)
from app.models.evaluation_plan import Rubric
from app.models.project import Project, ProjectStatus
from app.models.project_design import (
    EvaluationIndicator,
    GoalType,
    LearningGoal,
    SubjectContribution,
    SubjectRole,
)
from app.models.resource import Resource
from app.models.subject import Subject
from app.models.task import Task
from app.modules.ai_jobs import quality_rules, service
from app.modules.ai_jobs.quality_rules import IssueDraft


# ── 测试辅助 ──────────────────────────────────────────────────
def _make_project(db_session, creator_id="qr-teacher-1") -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title="质量规则测试项目",
        status=ProjectStatus.DRAFT,
        creator_id=creator_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


class _Actor:
    def __init__(self, user_id: str = "qr-teacher-1", role: str = "teacher"):
        self.id = user_id
        self.role = role
        self.school_id = None
        self.class_id = None
        self.is_active = True


def _add_subject(db_session, name: str) -> Subject:
    subject = Subject(id=str(uuid.uuid4()), name=name, is_active=True)
    db_session.add(subject)
    db_session.flush()
    return subject


def _add_contribution(db_session, project_id, subject_id, role: SubjectRole):
    contrib = SubjectContribution(
        project_id=project_id,
        subject_id=subject_id,
        role=role,
        knowledge="知识贡献",
        thinking="思维贡献",
        inquiry="探究贡献",
    )
    db_session.add(contrib)
    db_session.flush()
    return contrib


def _add_task(db_session, project_id, stage: TeachingStage, created_by="qr-teacher-1"):
    task = Task(
        project_id=project_id,
        title=f"任务-{stage.value}",
        created_by=created_by,
        stage=stage,
    )
    db_session.add(task)
    db_session.flush()
    return task


def _add_resource(db_session, project_id, tier: ResourceTier, uploaded_by="qr-teacher-1"):
    resource = Resource(
        project_id=project_id,
        title=f"资源-{tier.value}",
        res_type="document",
        uploaded_by=uploaded_by,
        tier=tier,
    )
    db_session.add(resource)
    db_session.flush()
    return resource


def _add_rubric(db_session, project_id, created_by="qr-teacher-1"):
    rubric = Rubric(
        project_id=project_id,
        version=1,
        is_current=True,
        created_by=created_by,
    )
    db_session.add(rubric)
    db_session.flush()
    return rubric


def _add_indicator(db_session, project_id):
    goal = LearningGoal(
        project_id=project_id,
        goal_type=GoalType.ABILITY,
        name="目标1",
    )
    db_session.add(goal)
    db_session.flush()
    indicator = EvaluationIndicator(
        goal_id=goal.id,
        project_id=project_id,
        observable_behavior="可观察行为",
    )
    db_session.add(indicator)
    db_session.flush()
    return indicator


def _add_active_provider(db_session):
    provider = AiProvider(
        id=str(uuid.uuid4()),
        name="qr-provider",
        api_url="https://fake.example/v1",
        model="fake-model",
        api_key="fake-key",
        status="active",
    )
    db_session.add(provider)
    db_session.commit()
    return provider


def _rule_codes(drafts: list[IssueDraft]) -> set[str]:
    return {d.rule_code.value for d in drafts}


# ── 学科拼盘（subject_mismatch）──────────────────────────────
class TestSubjectMismatch:
    """验收 2：AI 输出未体现核心学科 → BLOCKER subject_mismatch。"""

    def test_output_missing_core_subject_triggers_blocker(self, db_session):
        project = _make_project(db_session)
        math = _add_subject(db_session, "数学")
        _add_contribution(db_session, project.id, math.id, SubjectRole.CORE)
        db_session.commit()

        # AI 输出不含"数学"
        drafts, schema_valid = quality_rules.validate_output(
            db_session, project.id, "<p>这是一份语文教案</p>", "html"
        )
        assert schema_valid is True
        codes = _rule_codes(drafts)
        assert "subject_mismatch" in codes
        blocker = [d for d in drafts if d.rule_code.value == "subject_mismatch"][0]
        assert blocker.severity == QualitySeverity.BLOCKER

    def test_output_with_core_subject_no_mismatch(self, db_session):
        project = _make_project(db_session)
        math = _add_subject(db_session, "数学")
        _add_contribution(db_session, project.id, math.id, SubjectRole.CORE)
        db_session.commit()

        drafts, schema_valid = quality_rules.validate_output(
            db_session, project.id, "<p>数学跨学科教案：函数与艺术</p>", "html"
        )
        assert "subject_mismatch" not in _rule_codes(drafts)


# ── 贡献未使用（unused_contribution）────────────────────────
class TestUnusedContribution:
    """验收 2：支撑学科贡献未转化为任务或资源 → WARNING unused_contribution。"""

    def test_support_contribution_without_tasks_or_resources(self, db_session):
        project = _make_project(db_session)
        math = _add_subject(db_session, "数学")
        art = _add_subject(db_session, "美术")
        _add_contribution(db_session, project.id, math.id, SubjectRole.CORE)
        _add_contribution(db_session, project.id, art.id, SubjectRole.SUPPORT)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        assert "unused_contribution" in _rule_codes(drafts)
        warning = [d for d in drafts if d.rule_code.value == "unused_contribution"][0]
        assert warning.severity == QualitySeverity.WARNING

    def test_support_contribution_with_tasks_no_warning(self, db_session):
        project = _make_project(db_session)
        math = _add_subject(db_session, "数学")
        art = _add_subject(db_session, "美术")
        _add_contribution(db_session, project.id, math.id, SubjectRole.CORE)
        _add_contribution(db_session, project.id, art.id, SubjectRole.SUPPORT)
        _add_task(db_session, project.id, TeachingStage.IN_CLASS)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        assert "unused_contribution" not in _rule_codes(drafts)


# ── 三阶段缺失（missing_stage）──────────────────────────────
class TestMissingStage:
    """验收 2：课前/课中/课后三阶段任务链不完整 → BLOCKER missing_stage。"""

    def test_no_tasks_all_stages_missing(self, db_session):
        project = _make_project(db_session)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        stage_codes = [d for d in drafts if d.rule_code.value == "missing_stage"]
        assert len(stage_codes) == 3  # 三个阶段都缺
        assert all(d.severity == QualitySeverity.BLOCKER for d in stage_codes)

    def test_only_in_class_task_two_stages_missing(self, db_session):
        project = _make_project(db_session)
        _add_task(db_session, project.id, TeachingStage.IN_CLASS)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        stage_drafts = [d for d in drafts if d.rule_code.value == "missing_stage"]
        missing_stages = {d.object_ref for d in stage_drafts}
        assert "stage:pre_class" in missing_stages
        assert "stage:post_class" in missing_stages
        assert "stage:in_class" not in missing_stages

    def test_all_stages_present_no_missing(self, db_session):
        project = _make_project(db_session)
        _add_task(db_session, project.id, TeachingStage.PRE_CLASS)
        _add_task(db_session, project.id, TeachingStage.IN_CLASS)
        _add_task(db_session, project.id, TeachingStage.POST_CLASS)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        assert "missing_stage" not in _rule_codes(drafts)


# ── 资源层级缺失（missing_resource_tier）────────────────────
class TestMissingResourceTier:
    """验收 2：基础/提升/拓展三级资源不全 → BLOCKER missing_resource_tier。"""

    def test_no_resources_all_tiers_missing(self, db_session):
        project = _make_project(db_session)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        tier_drafts = [d for d in drafts if d.rule_code.value == "missing_resource_tier"]
        assert len(tier_drafts) == 3
        assert all(d.severity == QualitySeverity.BLOCKER for d in tier_drafts)

    def test_only_foundation_two_tiers_missing(self, db_session):
        project = _make_project(db_session)
        _add_resource(db_session, project.id, ResourceTier.FOUNDATION)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        tier_drafts = [d for d in drafts if d.rule_code.value == "missing_resource_tier"]
        missing_tiers = {d.object_ref for d in tier_drafts}
        assert "tier:enhancement" in missing_tiers
        assert "tier:extension" in missing_tiers
        assert "tier:foundation" not in missing_tiers

    def test_all_tiers_present_no_missing(self, db_session):
        project = _make_project(db_session)
        _add_resource(db_session, project.id, ResourceTier.FOUNDATION)
        _add_resource(db_session, project.id, ResourceTier.ENHANCEMENT)
        _add_resource(db_session, project.id, ResourceTier.EXTENSION)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        assert "missing_resource_tier" not in _rule_codes(drafts)


# ── 评价缺失（missing_evaluation）────────────────────────────
class TestMissingEvaluation:
    """验收 2：缺少量规或评价指标 → BLOCKER missing_evaluation。"""

    def test_no_rubric_no_indicator(self, db_session):
        project = _make_project(db_session)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        eval_drafts = [d for d in drafts if d.rule_code.value == "missing_evaluation"]
        assert len(eval_drafts) == 2  # 缺量规 + 缺指标
        assert all(d.severity == QualitySeverity.BLOCKER for d in eval_drafts)

    def test_has_rubric_but_no_indicator(self, db_session):
        project = _make_project(db_session)
        _add_rubric(db_session, project.id)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        eval_drafts = [d for d in drafts if d.rule_code.value == "missing_evaluation"]
        assert len(eval_drafts) == 1  # 仅缺指标
        assert "indicator" in eval_drafts[0].object_ref

    def test_has_rubric_and_indicator_no_missing(self, db_session):
        project = _make_project(db_session)
        _add_rubric(db_session, project.id)
        _add_indicator(db_session, project.id)
        db_session.commit()

        drafts = quality_rules.validate_project_context(db_session, project.id)
        assert "missing_evaluation" not in _rule_codes(drafts)


# ── 集成：通过 create_and_run_job 落库质量问题 ──────────────
class TestQualityIssuesPersisted:
    """验收 2 + 7：质量规则在 AI 任务创建时落库为 QualityIssue。"""

    def test_empty_project_produces_all_blockers(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            lambda provider, prompt, **kw: "<p>教案内容</p>",
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        from app.modules.ai_jobs.repository import list_issues_by_job

        issues = list_issues_by_job(db_session, job.id)
        codes = {i.rule_code.value for i in issues}
        # 空项目应触发全部项目级阻断规则
        assert "missing_stage" in codes
        assert "missing_resource_tier" in codes
        assert "missing_evaluation" in codes
        # 阻断级别
        blockers = [i for i in issues if i.severity == QualitySeverity.BLOCKER]
        assert len(blockers) >= 3

    def test_complete_project_produces_no_blockers(self, db_session, monkeypatch):
        """结构完整的项目不产生项目级阻断问题。"""
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        math = _add_subject(db_session, "数学")
        _add_contribution(db_session, project.id, math.id, SubjectRole.CORE)
        _add_task(db_session, project.id, TeachingStage.PRE_CLASS)
        _add_task(db_session, project.id, TeachingStage.IN_CLASS)
        _add_task(db_session, project.id, TeachingStage.POST_CLASS)
        _add_resource(db_session, project.id, ResourceTier.FOUNDATION)
        _add_resource(db_session, project.id, ResourceTier.ENHANCEMENT)
        _add_resource(db_session, project.id, ResourceTier.EXTENSION)
        _add_rubric(db_session, project.id)
        _add_indicator(db_session, project.id)
        db_session.commit()

        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            lambda provider, prompt, **kw: "<p>数学跨学科教案</p>",
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        from app.modules.ai_jobs.repository import count_open_blockers, list_issues_by_job

        assert count_open_blockers(db_session, job.id) == 0
        issues = list_issues_by_job(db_session, job.id)
        # 完整项目不应有项目级阻断（missing_stage/tier/evaluation）
        codes = {i.rule_code.value for i in issues}
        assert "missing_stage" not in codes
        assert "missing_resource_tier" not in codes
        assert "missing_evaluation" not in codes
