"""AI 任务生命周期测试（计划 Task 5 验收标准 1/5/6/7）。

覆盖：
- 验收 1：AI 状态机非法跃迁返回 409；超时映射 FAILED+TIMEOUT；失败重试；
  无效结构映射 FAILED+INVALID_OUTPUT；Provider 不可用映射 FAILED+PROVIDER_UNAVAILABLE。
- 验收 5：局部重生成创建新版本；采用状态流转。
- 验收 6：阻断问题未处理不能标记正式版本。
- 验收 7：全部使用假 Provider（monkeypatch _call_provider），不调用真实模型。

不伪造数据、不产生伪成功结果：Provider 不可用/超时/结构无效均落库为 FAILED，
不写入模拟内容或随机分。
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.exceptions import AppException
from app.models.ai_job import AiJob, AiOutputVersion, QualityIssue
from app.models.ai_provider import AiProvider
from app.models.enums import (
    AdoptionStatus,
    AiJobScene,
    AiJobStatus,
    IssueStatus,
    QualitySeverity,
)
from app.models.project import Project, ProjectStatus
from app.modules.ai_jobs import service
from app.modules.ai_jobs.repository import count_open_blockers, list_issues_by_job


# ── 测试辅助 ──────────────────────────────────────────────────
def _make_project(db_session, creator_id="ai-teacher-1") -> Project:
    project = Project(
        id=str(uuid.uuid4()),
        title="AI 治理测试项目",
        status=ProjectStatus.DRAFT,
        creator_id=creator_id,
        is_template=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


class _Actor:
    """轻量 actor 替身，避免依赖完整 User 注册流程。"""

    def __init__(self, user_id: str = "ai-teacher-1", role: str = "teacher"):
        self.id = user_id
        self.role = role
        self.school_id = None
        self.class_id = None
        self.is_active = True


def _add_active_provider(db_session, name="test-provider") -> AiProvider:
    provider = AiProvider(
        id=str(uuid.uuid4()),
        name=name,
        api_url="https://fake.example/v1",
        model="fake-model",
        api_key="fake-key",
        status="active",
    )
    db_session.add(provider)
    db_session.commit()
    return provider


def _fake_provider_returns(content: str):
    """返回一个 monkeypatch 替身，使 _call_provider 返回指定内容。"""

    def _stub(provider, prompt, **kwargs):
        return content

    return _stub


def _fake_provider_raises(exc: Exception):
    """返回一个 monkeypatch 替身，使 _call_provider 抛出指定异常。"""

    def _stub(provider, prompt, **kwargs):
        raise exc

    return _stub


def _resolve_all_blockers(db_session, actor, job_id: str) -> None:
    """处理任务全部阻断问题，使 adopt 可行（验收标准 6）。"""
    issues = list_issues_by_job(db_session, job_id)
    for issue in issues:
        if issue.severity == QualitySeverity.BLOCKER and issue.status == IssueStatus.OPEN:
            service.resolve_issue(
                db_session,
                actor,
                issue.id,
                resolution="测试中处理阻断问题",
                status=IssueStatus.RESOLVED,
            )


# ── 状态机非法跃迁 ────────────────────────────────────────────
class TestAiJobStateMachine:
    """验收 1：AI 状态机非法跃迁返回 409。"""

    def test_illegal_transition_from_succeeded_to_running(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>合法教案内容</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.SUCCEEDED

        # succeeded -> running 是非法跃迁
        with pytest.raises(AppException) as exc_info:
            service.transition_job(db_session, actor, job.id, AiJobStatus.RUNNING)
        assert exc_info.value.status_code == 409

    def test_illegal_transition_from_created_to_adopted(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        # 手动创建一个 created 状态任务（不执行）
        from app.models.ai_job import AiJob

        job = AiJob(
            project_id=project.id,
            scene=AiJobScene.LESSON_PLAN,
            status=AiJobStatus.CREATED,
            output_type="教案",
            initiated_by=actor.id,
            prompt_version="v1",
        )
        db_session.add(job)
        db_session.commit()

        with pytest.raises(AppException) as exc_info:
            service.transition_job(db_session, actor, job.id, AiJobStatus.ADOPTED)
        assert exc_info.value.status_code == 409

    def test_legal_transition_succeeded_to_reviewed(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>教案</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        reviewed = service.transition_job(
            db_session, actor, job.id, AiJobStatus.REVIEWED
        )
        assert reviewed.status == AiJobStatus.REVIEWED


# ── 超时 ─────────────────────────────────────────────────────
class TestAiJobTimeout:
    """验收 1：Provider 超时映射为 FAILED + TIMEOUT，并记录阻断质量问题。"""

    def test_timeout_marks_job_failed_with_timeout_code(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_raises(httpx.TimeoutException("连接超时")),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.FAILED
        assert job.error_code == "timeout"
        # 超时应记录为阻断质量问题
        issues = list_issues_by_job(db_session, job.id)
        timeout_issues = [i for i in issues if i.rule_code.value == "timeout"]
        assert len(timeout_issues) == 1
        assert timeout_issues[0].severity == QualitySeverity.BLOCKER


# ── 重试 ─────────────────────────────────────────────────────
class TestAiJobRetry:
    """验收 1：失败任务重试后可成功。"""

    def test_retry_failed_job_succeeds(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)

        # 第一次调用超时失败
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_raises(httpx.TimeoutException("首次超时")),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.FAILED

        # 重试时改为成功响应
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>重试成功教案</p>"),
        )
        retried = service.retry_job(db_session, actor, job.id)
        assert retried.status == AiJobStatus.SUCCEEDED
        assert retried.error_code is None
        # 重试成功后应产生新版本（首次失败不落库版本）
        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        assert len(versions) == 1
        assert versions[0].content == "<p>重试成功教案</p>"


# ── 无效结构 ─────────────────────────────────────────────────
class TestAiJobInvalidStructure:
    """验收 1：grading 场景 JSON 输出无效 → FAILED + INVALID_OUTPUT。"""

    def test_invalid_json_marks_job_failed(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        # grading 场景要求 JSON 输出；返回非法 JSON
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("这不是合法JSON {{{"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.GRADING, "评分结果"
        )
        assert job.status == AiJobStatus.FAILED
        assert job.error_code == "invalid_output"
        # 版本应标记为 schema_status=INVALID
        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        assert len(versions) == 1
        assert versions[0].schema_status.value == "invalid"


# ── Provider 不可用（内容拦截）──────────────────────────────
class TestAiJobProviderUnavailable:
    """验收 1/7：无可用 Provider 时 FAILED + PROVIDER_UNAVAILABLE，不产生伪成功。"""

    def test_no_provider_marks_job_failed(self, db_session):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        # 不创建任何 active Provider（autouse fixture 已禁用全部）
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.FAILED
        assert job.error_code == "provider_unavailable"
        # 不应产生任何输出版本（不伪造内容）
        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        assert len(versions) == 0


# ── 完整生命周期 ─────────────────────────────────────────────
class TestAiJobFullLifecycle:
    """验收 5：created → running → succeeded → reviewed → adopted。"""

    def test_full_lifecycle_create_review_adopt(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>完整生命周期教案</p>"),
        )

        # 1. 创建并执行 → SUCCEEDED
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.SUCCEEDED

        # 2. 审核 → REVIEWED
        reviewed = service.review_job(db_session, actor, job.id, note="内容合格")
        assert reviewed.status == AiJobStatus.REVIEWED
        assert reviewed.reviewed_by == actor.id

        # 3. 处理全部阻断问题（验收 6：阻断问题处理后才可正式发布）
        _resolve_all_blockers(db_session, actor, job.id)
        assert count_open_blockers(db_session, job.id) == 0

        # 4. 采用 → ADOPTED
        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        version_id = versions[0].id
        adopted = service.adopt_job(
            db_session,
            actor,
            job.id,
            version_id,
            AdoptionStatus.ADOPTED,
            note="正式采用",
        )
        assert adopted.status == AiJobStatus.ADOPTED
        assert adopted.adopted_version_id == version_id
        # 版本应标记为最终版本
        db_session.refresh(versions[0])
        assert versions[0].is_final is True
        assert versions[0].adoption_status == AdoptionStatus.ADOPTED


# ── 阻断问题未处理不能采用 ───────────────────────────────────
class TestAdoptionBlockedByOpenIssues:
    """验收 6：阻断问题未处理不能标记正式版本。"""

    def test_adopt_blocked_when_open_blockers_exist(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>教案</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        # 空项目结构必然产生阻断问题（missing_stage/missing_resource_tier/missing_evaluation）
        assert count_open_blockers(db_session, job.id) > 0

        service.review_job(db_session, actor, job.id)

        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        with pytest.raises(AppException) as exc_info:
            service.adopt_job(
                db_session,
                actor,
                job.id,
                versions[0].id,
                AdoptionStatus.ADOPTED,
            )
        assert exc_info.value.status_code == 409
        assert "阻断" in exc_info.value.message

    def test_adopt_allowed_after_resolving_blockers(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>教案</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        service.review_job(db_session, actor, job.id)
        _resolve_all_blockers(db_session, actor, job.id)
        assert count_open_blockers(db_session, job.id) == 0

        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        adopted = service.adopt_job(
            db_session, actor, job.id, versions[0].id, AdoptionStatus.ADOPTED
        )
        assert adopted.status == AiJobStatus.ADOPTED


# ── 局部重生成 ───────────────────────────────────────────────
class TestAiJobRegenerate:
    """验收 5：局部重生成创建新版本。"""

    def test_regenerate_creates_new_version(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>第一版教案</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        from app.modules.ai_jobs.repository import list_versions_by_job

        v1_list = list_versions_by_job(db_session, job.id)
        assert len(v1_list) == 1

        # 切换假响应后重生成
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>第二版教案（重生成）</p>"),
        )
        v2 = service.regenerate_job(
            db_session, actor, job.id, base_version_id=v1_list[0].id, note="加强学科融合"
        )
        assert v2.version == 2
        assert v2.regenerated_from == v1_list[0].id
        assert "重生成" in v2.content
        assert v2.teacher_note == "加强学科融合"

        all_versions = list_versions_by_job(db_session, job.id)
        assert len(all_versions) == 2

    def test_regenerate_blocked_in_wrong_status(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_raises(httpx.TimeoutException("超时")),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.status == AiJobStatus.FAILED
        with pytest.raises(AppException) as exc_info:
            service.regenerate_job(db_session, actor, job.id)
        assert exc_info.value.status_code == 409


# ── 输入摘要留存（阶段验收）──────────────────────────────────
class TestAiJobInputSummaryRetention:
    """阶段验收：AI 内容均有输入摘要、模型、提示版本、原始输出。"""

    def test_job_records_input_summary_model_prompt_version(self, db_session, monkeypatch):
        project = _make_project(db_session)
        actor = _Actor(user_id=project.creator_id)
        provider = _add_active_provider(db_session)
        monkeypatch.setattr(
            "app.modules.ai_jobs.service._call_provider",
            _fake_provider_returns("<p>带元数据教案</p>"),
        )
        job = service.create_and_run_job(
            db_session, actor, project.id, AiJobScene.LESSON_PLAN, "教案"
        )
        assert job.input_summary is not None
        assert "problem" in job.input_summary
        assert job.provider_id == provider.id
        assert job.provider_model == provider.model
        assert job.prompt_version == "v1"
        # 原始输出留存于版本
        from app.modules.ai_jobs.repository import list_versions_by_job

        versions = list_versions_by_job(db_session, job.id)
        assert len(versions) == 1
        assert versions[0].content == "<p>带元数据教案</p>"
