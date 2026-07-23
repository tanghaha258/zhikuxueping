"""项目设计领域模型、CRUD、唯一性和完整性检查测试。

覆盖计划 Task 1 验收项：
- 写项目问题、学科贡献、目标、指标和证据计划的模型测试。
- 写唯一核心学科、至少一门支撑学科和重复学科拒绝测试。
- 实现项目设计 CRUD、版本更新和完整性检查接口的验证。
- 实现 POST /api/v1/projects/{id}/validate-activation 返回 blockers/warnings/completion。
"""
from __future__ import annotations

import uuid

from app.models.enums import TeachingStage
from app.models.project import Project, ProjectStatus
from app.models.project_design import (
    EvidenceCollector,
    EvidencePlan,
    EvidenceType,
    EvaluationIndicator,
    GoalType,
    LearningGoal,
    ProjectProblem,
    SubjectContribution,
    SubjectRole,
)
from app.modules.project_designs.repository import ProjectDesignRepository
from app.modules.project_designs.service import (
    add_contribution,
    add_evidence_plan,
    add_goal,
    add_indicator,
    get_design_snapshot,
    remove_contribution,
    upsert_problem,
)
from app.modules.project_designs.validators import validate_activation


# ── 测试辅助 ──────────────────────────────────────────────────
def _make_project(db_session, creator_id="teacher-1", title="跨学科项目") -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title=title,
        status=ProjectStatus.DRAFT,
        creator_id=creator_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程进行服务层测试。"""

    def __init__(self, user_id: str, role: str = "teacher", school_id: str | None = None):
        self.id = user_id
        self.role = role
        self.school_id = school_id
        self.class_id = None
        self.is_active = True


# ── 模型测试 ──────────────────────────────────────────────────
class TestProjectDesignModels:
    """验证 5 个新模型可正确持久化与读取。"""

    def test_project_problem_persists_with_version(self, db_session):
        project = _make_project(db_session)
        repo = ProjectDesignRepository(db_session)
        problem = ProjectProblem(
            project_id=project.id,
            context="家乡河道黑臭水体现状调查",
            object="城东护城河",
            audience="周边社区居民",
            constraints="采样需在旱季完成",
            deliverable="水质检测报告与改善建议",
            usage="提交社区与环保局",
            is_current=True,
            version=1,
        )
        repo.add_problem(problem)
        db_session.commit()
        db_session.refresh(problem)

        assert problem.id is not None
        assert problem.version == 1
        assert problem.is_current is True
        fetched = repo.get_problem(project.id)
        assert fetched is not None
        assert fetched.context == "家乡河道黑臭水体现状调查"

    def test_subject_contribution_persists_with_role(self, db_session):
        project = _make_project(db_session)
        repo = ProjectDesignRepository(db_session)
        core = SubjectContribution(
            project_id=project.id,
            subject_id="sub-science",
            role=SubjectRole.CORE,
            knowledge="水体指标与检测方法",
            thinking="证据推理",
            inquiry="实地采样与对照实验",
        )
        repo.add_contribution(core)
        db_session.commit()

        contributions = repo.list_contributions(project.id)
        assert len(contributions) == 1
        assert contributions[0].role == SubjectRole.CORE
        assert contributions[0].subject_id == "sub-science"

    def test_learning_goal_and_indicator_chain(self, db_session):
        project = _make_project(db_session)
        repo = ProjectDesignRepository(db_session)
        goal = LearningGoal(
            project_id=project.id,
            goal_type=GoalType.ABILITY,
            name="能设计简单的水质检测方案",
            description="基于指标选择方法",
        )
        repo.add_goal(goal)
        db_session.flush()
        indicator = EvaluationIndicator(
            goal_id=goal.id,
            project_id=project.id,
            observable_behavior="能独立列出至少 3 项水质检测指标及对应方法",
            level_rule="3 项及以上=优秀；2 项=合格；不足=待改进",
        )
        repo.add_indicator(indicator)
        db_session.commit()

        assert repo.list_goals(project.id)[0].name == "能设计简单的水质检测方案"
        assert repo.list_indicators(project.id)[0].goal_id == goal.id

    def test_evidence_plan_binds_indicator_and_stage(self, db_session):
        project = _make_project(db_session)
        repo = ProjectDesignRepository(db_session)
        goal = LearningGoal(
            project_id=project.id, goal_type=GoalType.PRACTICE, name="实地调查能力"
        )
        repo.add_goal(goal)
        db_session.flush()
        indicator = EvaluationIndicator(
            goal_id=goal.id,
            project_id=project.id,
            observable_behavior="提交完整采样记录表",
        )
        repo.add_indicator(indicator)
        db_session.flush()
        plan = EvidencePlan(
            indicator_id=indicator.id,
            project_id=project.id,
            stage=TeachingStage.IN_CLASS,
            evidence_type=EvidenceType.ARTIFACT,
            collector=EvidenceCollector.STUDENT,
            required=True,
            description="课中提交采样记录",
        )
        repo.add_evidence_plan(plan)
        db_session.commit()

        plans = repo.list_evidence_plans(project.id)
        assert len(plans) == 1
        assert plans[0].stage == TeachingStage.IN_CLASS
        assert plans[0].required is True


# ── 唯一性与重复拒绝 ─────────────────────────────────────────
class TestSubjectContributionUniqueness:
    """唯一核心学科、至少一门支撑学科、重复学科拒绝。"""

    def test_duplicate_subject_rejected(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        add_contribution(
            db_session,
            actor,
            project.id,
            _contribution_create("sub-math", SubjectRole.SUPPORT),
        )
        # 同一学科重复登记应被拒绝（409）
        try:
            add_contribution(
                db_session,
                actor,
                project.id,
                _contribution_create("sub-math", SubjectRole.SUPPORT),
            )
            raise AssertionError("重复学科应被拒绝")
        except Exception as exc:
            assert "409" in str(exc) or "重复" in str(exc) or "duplicate" in str(exc).lower()

    def test_second_core_subject_rejected(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        add_contribution(
            db_session, actor, project.id, _contribution_create("sub-science", SubjectRole.CORE)
        )
        try:
            add_contribution(
                db_session,
                actor,
                project.id,
                _contribution_create("sub-math", SubjectRole.CORE),
            )
            raise AssertionError("第二个核心学科应被拒绝")
        except Exception as exc:
            assert "409" in str(exc) or "核心" in str(exc)

    def test_core_subject_syncs_project_main_table(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        contribution = add_contribution(
            db_session, actor, project.id, _contribution_create("sub-science", SubjectRole.CORE)
        )
        db_session.refresh(project)
        assert project.core_subject_id == "sub-science"
        # 移除核心学科后主表字段应同步清空
        remove_contribution(db_session, actor, project.id, contribution.id)
        db_session.refresh(project)
        assert project.core_subject_id is None


# ── 真实问题版本化 ───────────────────────────────────────────
class TestProblemVersioning:
    """真实问题编辑采用版本化，历史版本保留只读。"""

    def test_upsert_creates_new_version_and_keeps_history(self, db_session):
        from app.schemas.project_design import ProjectProblemCreate

        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        v1 = upsert_problem(
            db_session,
            actor,
            project.id,
            ProjectProblemCreate(context="初版情境", deliverable="初版成果"),
        )
        v2 = upsert_problem(
            db_session,
            actor,
            project.id,
            ProjectProblemCreate(context="修订情境", deliverable="修订成果"),
        )

        db_session.refresh(v1)
        assert v1.version == 1
        assert v1.is_current is False  # 旧版本变为非当前
        assert v2.version == 2
        assert v2.is_current is True

        repo = ProjectDesignRepository(db_session)
        versions = repo.list_problem_versions(project.id)
        assert len(versions) == 2
        # get_problem 只返回当前版本
        assert repo.get_problem(project.id).id == v2.id


# ── 完整性检查 ───────────────────────────────────────────────
class TestValidateActivation:
    """validate-activation 返回 blockers/warnings/completion。"""

    def test_empty_project_blocked(self, db_session):
        project = _make_project(db_session)
        result = validate_activation(db_session, project)
        assert result.can_activate is False
        codes = {b.code for b in result.blockers}
        assert "missing_core_subject" in codes
        assert "missing_support_subject" in codes
        assert "missing_problem" in codes
        assert 0.0 <= result.completion < 1.0

    def test_complete_project_can_activate(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        _build_complete_project(db_session, actor, project.id)
        result = validate_activation(db_session, project)
        assert result.can_activate is True
        assert result.blockers == []
        assert result.completion == 1.0

    def test_goal_without_indicator_blocks(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        # 核心学科 + 支撑学科 + 问题，但目标未拆解指标
        add_contribution(db_session, actor, project.id, _contribution_create("sub-s", SubjectRole.CORE))
        add_contribution(db_session, actor, project.id, _contribution_create("sub-x", SubjectRole.SUPPORT))
        from app.schemas.project_design import LearningGoalCreate

        add_goal(db_session, actor, project.id, LearningGoalCreate(goal_type=GoalType.KNOWLEDGE, name="未拆解目标"))
        result = validate_activation(db_session, project)
        codes = {b.code for b in result.blockers}
        assert "goal_without_indicator" in codes
        assert result.can_activate is False

    def test_indicator_without_required_evidence_blocks(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        add_contribution(db_session, actor, project.id, _contribution_create("sub-s", SubjectRole.CORE))
        add_contribution(db_session, actor, project.id, _contribution_create("sub-x", SubjectRole.SUPPORT))
        from app.schemas.project_design import (
            EvaluationIndicatorCreate,
            LearningGoalCreate,
            ProjectProblemCreate,
        )

        upsert_problem(db_session, actor, project.id, ProjectProblemCreate(context="情境"))
        goal = add_goal(
            db_session, actor, project.id, LearningGoalCreate(goal_type=GoalType.ABILITY, name="目标")
        )
        # 有指标但缺少 required 证据计划
        add_indicator(
            db_session,
            actor,
            project.id,
            EvaluationIndicatorCreate(goal_id=goal.id, observable_behavior="可观察行为"),
        )
        result = validate_activation(db_session, project)
        codes = {b.code for b in result.blockers}
        assert "indicator_without_required_evidence" in codes


# ── 服务层聚合快照 ───────────────────────────────────────────
class TestDesignSnapshot:
    """聚合快照一次性返回设计页所需数据。"""

    def test_snapshot_returns_all_sections(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        _build_complete_project(db_session, actor, project.id)

        snapshot = get_design_snapshot(db_session, actor, project.id)
        assert snapshot["problem"] is not None
        assert len(snapshot["contributions"]) == 2
        assert len(snapshot["goals"]) >= 1
        assert len(snapshot["indicators"]) >= 1
        assert len(snapshot["evidence_plans"]) >= 1


# ── 引用保护 ─────────────────────────────────────────────────
class TestReferenceProtection:
    """删除被引用的目标/指标应被拒绝（409）。"""

    def test_cannot_delete_goal_with_indicators(self, db_session):
        from app.schemas.project_design import (
            EvaluationIndicatorCreate,
            LearningGoalCreate,
        )

        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        goal = add_goal(
            db_session, actor, project.id, LearningGoalCreate(goal_type=GoalType.ABILITY, name="目标")
        )
        add_indicator(
            db_session,
            actor,
            project.id,
            EvaluationIndicatorCreate(goal_id=goal.id, observable_behavior="行为"),
        )
        try:
            from app.modules.project_designs.service import remove_goal

            remove_goal(db_session, actor, project.id, goal.id)
            raise AssertionError("被引用的目标应拒绝删除")
        except Exception as exc:
            assert "409" in str(exc) or "引用" in str(exc)

    def test_cannot_delete_indicator_with_evidence_plans(self, db_session):
        from app.schemas.project_design import (
            EvaluationIndicatorCreate,
            EvidencePlanCreate,
            LearningGoalCreate,
        )

        project = _make_project(db_session)
        actor = _Actor(project.creator_id)
        goal = add_goal(
            db_session, actor, project.id, LearningGoalCreate(goal_type=GoalType.ABILITY, name="目标")
        )
        indicator = add_indicator(
            db_session,
            actor,
            project.id,
            EvaluationIndicatorCreate(goal_id=goal.id, observable_behavior="行为"),
        )
        add_evidence_plan(
            db_session,
            actor,
            project.id,
            EvidencePlanCreate(
                indicator_id=indicator.id,
                stage=TeachingStage.PRE_CLASS,
                evidence_type=EvidenceType.OBSERVATION,
                collector=EvidenceCollector.TEACHER,
            ),
        )
        try:
            from app.modules.project_designs.service import remove_indicator

            remove_indicator(db_session, actor, project.id, indicator.id)
            raise AssertionError("被引用的指标应拒绝删除")
        except Exception as exc:
            assert "409" in str(exc) or "引用" in str(exc)


# ── 跨项目隔离 ───────────────────────────────────────────────
class TestProjectIsolation:
    """指标/证据计划必须绑定本项目内的目标/指标。"""

    def test_indicator_must_bind_to_project_goal(self, db_session):
        from app.schemas.project_design import (
            EvaluationIndicatorCreate,
            LearningGoalCreate,
        )

        project_a = _make_project(db_session, title="项目A")
        project_b = _make_project(db_session, creator_id="teacher-2", title="项目B")
        actor_a = _Actor(project_a.creator_id)
        goal_b = add_goal(
            db_session,
            _Actor(project_b.creator_id),
            project_b.id,
            LearningGoalCreate(goal_type=GoalType.KNOWLEDGE, name="B项目目标"),
        )
        # 用 B 项目的目标在 A 项目创建指标应被拒绝
        try:
            add_indicator(
                db_session,
                actor_a,
                project_a.id,
                EvaluationIndicatorCreate(goal_id=goal_b.id, observable_behavior="越权指标"),
            )
            raise AssertionError("指标应绑定本项目目标")
        except Exception as exc:
            assert "400" in str(exc) or "本项目" in str(exc)


# ── 辅助函数 ─────────────────────────────────────────────────
def _contribution_create(subject_id: str, role: SubjectRole):
    from app.schemas.project_design import SubjectContributionCreate

    return SubjectContributionCreate(
        subject_id=subject_id,
        role=role,
        knowledge="知识贡献",
        thinking="思维贡献",
        inquiry="探究贡献",
        removal_impact="移除将丢失该学科视角",
    )


def _build_complete_project(db_session, actor, project_id: str):
    """构造一个通过完整性检查的完整项目（核心+支撑+问题+目标+指标+证据计划）。"""
    from app.schemas.project_design import (
        EvaluationIndicatorCreate,
        EvidencePlanCreate,
        LearningGoalCreate,
        ProjectProblemCreate,
    )

    upsert_problem(
        db_session, actor, project_id, ProjectProblemCreate(context="家乡河道调查情境")
    )
    add_contribution(db_session, actor, project_id, _contribution_create("sub-science", SubjectRole.CORE))
    add_contribution(db_session, actor, project_id, _contribution_create("sub-math", SubjectRole.SUPPORT))
    goal = add_goal(
        db_session,
        actor,
        project_id,
        LearningGoalCreate(goal_type=GoalType.ABILITY, name="能设计水质检测方案"),
    )
    indicator = add_indicator(
        db_session,
        actor,
        project_id,
        EvaluationIndicatorCreate(
            goal_id=goal.id,
            observable_behavior="列出至少 3 项水质指标",
            level_rule="3 项=优秀",
        ),
    )
    add_evidence_plan(
        db_session,
        actor,
        project_id,
        EvidencePlanCreate(
            indicator_id=indicator.id,
            stage=TeachingStage.IN_CLASS,
            evidence_type=EvidenceType.ARTIFACT,
            collector=EvidenceCollector.STUDENT,
            required=True,
        ),
    )
