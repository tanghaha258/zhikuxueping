"""AI 治理领域服务层（计划 Task 5）。

职责：
- 聚合项目结构化上下文作为 AI 输入摘要（验收标准 4：不由页面重复录入）。
- 执行 AI 任务状态机：created -> queued -> running -> succeeded/failed
  -> reviewed -> adopted/rejected；非法跃迁返回 409。
- 调用 Provider 失败统一映射到 AiErrorCode，不产生模拟分或伪成功结果。
- 落库输出版本与质量问题；阻断问题未处理不能标记正式版本（验收标准 6）。
- 支持局部重生成与版本对比（验收标准 5）。

唯一提交点在服务层；失败回滚。
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.ai_job import AiJob, AiOutputVersion, QualityIssue
from app.models.ai_provider import AiProvider
from app.models.enums import (
    AdoptionStatus,
    AiJobScene,
    AiJobStatus,
    IssueStatus,
    QualityRuleCode,
    QualitySeverity,
    SchemaStatus,
)
from app.models.evaluation_plan import Rubric
from app.models.project_design import (
    EvaluationIndicator,
    EvidencePlan,
    LearningGoal,
    ProjectProblem,
    SubjectContribution,
)
from app.models.resource import Resource
from app.models.task import Task
from app.models.user import User
from app.modules.ai_gateway import complete
from app.modules.ai_gateway.errors import AiErrorCode
from app.modules.ai_jobs import policy, quality_rules, repository
from app.modules.ai_jobs.quality_rules import IssueDraft


# ── 状态机（计划 4.3）────────────────────────────────────────
_TRANSITIONS: dict[AiJobStatus, set[AiJobStatus]] = {
    AiJobStatus.CREATED: {AiJobStatus.QUEUED, AiJobStatus.RUNNING},
    AiJobStatus.QUEUED: {AiJobStatus.RUNNING, AiJobStatus.CREATED},
    AiJobStatus.RUNNING: {AiJobStatus.SUCCEEDED, AiJobStatus.FAILED},
    AiJobStatus.SUCCEEDED: {AiJobStatus.REVIEWED},
    AiJobStatus.FAILED: {AiJobStatus.REVIEWED, AiJobStatus.QUEUED},
    AiJobStatus.REVIEWED: {AiJobStatus.ADOPTED, AiJobStatus.REJECTED},
    AiJobStatus.ADOPTED: set(),
    AiJobStatus.REJECTED: set(),
}


def _validate_transition(current: AiJobStatus, target: AiJobStatus) -> None:
    allowed = _TRANSITIONS.get(current, set())
    if target not in allowed:
        raise AppException(
            code=40901,
            message=(
                f"AI 任务状态非法跃迁：当前「{current.value}」，"
                f"目标「{target.value}」，允许："
                f"{','.join(s.value for s in allowed) or '无（终态）'}"
            ),
            status_code=409,
        )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


# ── 项目上下文聚合（验收标准 4）──────────────────────────────
def build_project_context(db: Session, project_id: str) -> dict[str, Any]:
    """聚合项目结构化上下文，作为 AI 输入摘要。

    覆盖真实问题、学科贡献、学习目标、评价指标、证据计划、
    三级资源、三阶段任务链与量规，避免页面重复录入。
    """
    problem = db.execute(
        select(ProjectProblem).where(
            ProjectProblem.project_id == project_id,
            ProjectProblem.is_current.is_(True),
        )
    ).scalars().first()
    contributions = list(
        db.execute(
            select(SubjectContribution).where(
                SubjectContribution.project_id == project_id
            )
        ).scalars().all()
    )
    goals = list(
        db.execute(
            select(LearningGoal).where(LearningGoal.project_id == project_id)
        ).scalars().all()
    )
    indicators = list(
        db.execute(
            select(EvaluationIndicator).where(
                EvaluationIndicator.project_id == project_id
            )
        ).scalars().all()
    )
    evidence_plans = list(
        db.execute(
            select(EvidencePlan).where(EvidencePlan.project_id == project_id)
        ).scalars().all()
    )
    resources = list(
        db.execute(
            select(Resource).where(Resource.project_id == project_id)
        ).scalars().all()
    )
    tasks = list(
        db.execute(select(Task).where(Task.project_id == project_id)).scalars().all()
    )
    rubric = db.execute(
        select(Rubric).where(
            Rubric.project_id == project_id, Rubric.is_current.is_(True)
        )
    ).scalars().first()
    return {
        "problem": _problem_summary(problem),
        "contributions": [_contribution_summary(c) for c in contributions],
        "goals": [{"id": g.id, "name": g.name, "type": _enum_value(g.goal_type)} for g in goals],
        "indicators": [
            {"id": i.id, "goal_id": i.goal_id, "behavior": i.observable_behavior}
            for i in indicators
        ],
        "evidence_plans": [
            {
                "id": p.id,
                "indicator_id": p.indicator_id,
                "stage": _enum_value(p.stage),
                "required": p.required,
            }
            for p in evidence_plans
        ],
        "resources": [
            {
                "id": r.id,
                "title": r.title,
                "tier": _enum_value(r.tier),
                "stage": _enum_value(r.stage),
            }
            for r in resources
        ],
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "stage": _enum_value(t.stage),
                "tier": _enum_value(t.tier),
            }
            for t in tasks
        ],
        "rubric": {"id": rubric.id, "version": rubric.version} if rubric else None,
    }


def _problem_summary(problem: ProjectProblem | None) -> dict | None:
    if not problem:
        return None
    return {
        "context": problem.context,
        "object": problem.object,
        "audience": problem.audience,
        "constraints": problem.constraints,
        "deliverable": problem.deliverable,
        "usage": problem.usage,
    }


def _contribution_summary(c: SubjectContribution) -> dict:
    return {
        "subject_id": c.subject_id,
        "role": _enum_value(c.role),
        "knowledge": c.knowledge,
        "thinking": c.thinking,
        "inquiry": c.inquiry,
    }


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


# ── Provider 调用点（便于测试 mock）──────────────────────────
def _call_provider(
    provider: AiProvider,
    prompt: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: float = 60.0,
) -> str:
    """调用 AI Provider，返回原始内容字符串。

    测试通过 monkeypatch 此函数注入假响应，不调用真实模型（验收标准 7）。
    """
    return complete(
        provider.api_url,
        provider.api_key,
        provider.model,
        [{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def _build_prompt(scene: AiJobScene, context: dict[str, Any], output_type: str) -> str:
    """根据场景与项目上下文构造提示词。"""
    problem = context.get("problem") or {}
    contributions = context.get("contributions") or []
    goals = context.get("goals") or []
    tasks = context.get("tasks") or []
    subject_line = "、".join(
        c.get("role", "") + ":" + c.get("subject_id", "") for c in contributions
    ) or "未指定"
    goals_line = "；".join(g.get("name", "") for g in goals) or "未指定"
    tasks_line = "；".join(t.get("title", "") for t in tasks) or "未指定"
    return (
        f"你是跨学科教学设计专家，请基于以下项目上下文生成「{output_type}」。\n"
        f"真实问题：{problem.get('object', '未指定')}（受众：{problem.get('audience', '未指定')}）\n"
        f"学科贡献：{subject_line}\n"
        f"学习目标：{goals_line}\n"
        f"任务链：{tasks_line}\n"
        f"请确保内容紧扣核心学科与真实问题，结构完整。"
    )


# ── 创建并执行任务 ───────────────────────────────────────────
def create_and_run_job(
    db: Session,
    actor: User,
    project_id: str,
    scene: AiJobScene,
    output_type: str,
    *,
    task_id: str | None = None,
    submission_id: str | None = None,
) -> AiJob:
    """创建 AI 任务并同步执行，返回任务对象。"""
    policy.ensure_can_create_job(db, actor, project_id)
    context = build_project_context(db, project_id)
    job = AiJob(
        project_id=project_id,
        scene=scene,
        status=AiJobStatus.CREATED,
        output_type=output_type,
        input_summary=context,
        initiated_by=actor.id,
        task_id=task_id,
        submission_id=submission_id,
        prompt_version="v1",
    )
    repository.create_job(db, job)
    # 落库项目级质量规则（验收标准 2）
    drafts = quality_rules.validate_project_context(db, project_id)
    _persist_issue_drafts(db, drafts, job_id=job.id, version_id=None)
    # 执行
    job.status = AiJobStatus.RUNNING
    db.flush()
    _execute_job(db, job, context)
    _commit(db)
    db.refresh(job)
    return job


def _execute_job(db: Session, job: AiJob, context: dict[str, Any]) -> None:
    """执行 AI 调用、落库输出版本与版本级质量问题，更新任务状态。"""
    provider = repository.get_active_provider(db)
    start = time.monotonic()
    try:
        if not provider:
            raise AppException(
                code=50001,
                message="AI Provider 不可用",
                status_code=500,
            )
        job.provider_id = provider.id
        job.provider_model = provider.model
        prompt = _build_prompt(job.scene, context, job.output_type)
        content = _call_provider(provider, prompt)
        duration_ms = int((time.monotonic() - start) * 1000)
        job.duration_ms = duration_ms
        # 落库输出版本
        content_type = _content_type_for_scene(job.scene)
        version = AiOutputVersion(
            job_id=job.id,
            version=repository.next_version_number(db, job.id),
            content=content,
            content_type=content_type,
            schema_status=SchemaStatus.PENDING,
        )
        repository.create_version(db, version)
        # 版本级质量校验
        drafts, schema_valid = quality_rules.validate_output(
            db, job.project_id, content, content_type
        )
        version.schema_status = SchemaStatus.VALID if schema_valid else SchemaStatus.INVALID
        if not schema_valid:
            version.schema_errors = [d.message for d in drafts]
        _persist_issue_drafts(db, drafts, job_id=job.id, version_id=version.id)
        # 结构无效视为失败（不产生可采纳结果）
        if not schema_valid:
            job.status = AiJobStatus.FAILED
            job.error_code = AiErrorCode.INVALID_OUTPUT.value
            job.error_message = "AI 输出结构无效"
        else:
            job.status = AiJobStatus.SUCCEEDED
            job.error_code = None
            job.error_message = None
    except httpx.TimeoutException:
        job.status = AiJobStatus.FAILED
        job.error_code = AiErrorCode.TIMEOUT.value
        job.error_message = "AI 调用超时"
        _record_timeout_issue(db, job.id)
    except AppException:
        # Provider 不可用
        job.status = AiJobStatus.FAILED
        job.error_code = AiErrorCode.PROVIDER_UNAVAILABLE.value
        job.error_message = "AI Provider 不可用，请配置后重试"
    except Exception as exc:
        job.status = AiJobStatus.FAILED
        job.error_code = AiErrorCode.PROVIDER_UNAVAILABLE.value
        job.error_message = str(exc)[:200]
    db.flush()


def _content_type_for_scene(scene: AiJobScene) -> str:
    """grading 场景输出 JSON，其余场景输出 HTML/文本。"""
    return "json" if scene == AiJobScene.GRADING else "html"


def _record_timeout_issue(db: Session, job_id: str) -> None:
    """超时记录为阻断质量问题，便于教师处理。"""
    repository.create_issue(
        db,
        QualityIssue(
            job_id=job_id,
            severity=QualitySeverity.BLOCKER,
            rule_code=QualityRuleCode.TIMEOUT,
            object_ref=f"job:{job_id}",
            message="AI 调用超时，需重试或人工兜底",
        ),
    )


def _persist_issue_drafts(
    db: Session,
    drafts: list[IssueDraft],
    *,
    job_id: str | None,
    version_id: str | None,
) -> None:
    for draft in drafts:
        repository.create_issue(
            db,
            QualityIssue(
                job_id=job_id,
                version_id=version_id,
                severity=draft.severity,
                rule_code=draft.rule_code,
                object_ref=draft.object_ref,
                message=draft.message,
            ),
        )


# ── 状态机迁移 ───────────────────────────────────────────────
def transition_job(db: Session, actor: User, job_id: str, target: AiJobStatus) -> AiJob:
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_manage_job(db, actor, job)
    if not isinstance(target, AiJobStatus):
        raise AppException(code=40001, message="无效的目标状态", status_code=400)
    _validate_transition(job.status, target)
    job.status = target
    _commit(db)
    db.refresh(job)
    return job


def retry_job(db: Session, actor: User, job_id: str) -> AiJob:
    """重试失败任务：failed -> queued -> running -> 重新执行。"""
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_manage_job(db, actor, job)
    _validate_transition(job.status, AiJobStatus.QUEUED)
    job.status = AiJobStatus.QUEUED
    db.flush()
    job.status = AiJobStatus.RUNNING
    db.flush()
    context = job.input_summary or build_project_context(db, job.project_id)
    _execute_job(db, job, context)
    _commit(db)
    db.refresh(job)
    return job


# ── 教师审核 ─────────────────────────────────────────────────
def review_job(db: Session, actor: User, job_id: str, note: str | None = None) -> AiJob:
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_manage_job(db, actor, job)
    _validate_transition(job.status, AiJobStatus.REVIEWED)
    job.status = AiJobStatus.REVIEWED
    job.reviewed_by = actor.id
    job.reviewed_at = datetime.now(timezone.utc)
    if note and job.adopted_version_id:
        version = repository.get_version(db, job.adopted_version_id)
        if version:
            version.teacher_note = note
    _commit(db)
    db.refresh(job)
    return job


def adopt_job(
    db: Session,
    actor: User,
    job_id: str,
    version_id: str,
    adoption_status: AdoptionStatus,
    note: str | None = None,
) -> AiJob:
    """教师采用/拒绝输出版本。

    阻断性问题未处理时不能标记 adopted（验收标准 6）。
    """
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_manage_job(db, actor, job)
    version = repository.get_version(db, version_id)
    if not version or version.job_id != job.id:
        raise AppException(code=40401, message="输出版本不存在", status_code=404)
    # 采用前必须先审核
    _validate_transition(job.status, AiJobStatus.ADOPTED if adoption_status == AdoptionStatus.ADOPTED else AiJobStatus.REJECTED)

    if adoption_status == AdoptionStatus.ADOPTED:
        # 阻断问题未处理不能标记正式版本
        open_blockers = repository.count_open_blockers(db, job.id)
        if open_blockers > 0:
            raise AppException(
                code=40901,
                message=f"存在 {open_blockers} 个未处理阻断问题，不能标记正式版本",
                status_code=409,
            )
        job.status = AiJobStatus.ADOPTED
        job.adopted_by = actor.id
        job.adopted_at = datetime.now(timezone.utc)
        job.adopted_version_id = version.id
        version.adoption_status = AdoptionStatus.ADOPTED
        version.is_final = True
        version.teacher_note = note
    elif adoption_status == AdoptionStatus.PARTIALLY_ADOPTED:
        job.status = AiJobStatus.ADOPTED
        job.adopted_by = actor.id
        job.adopted_at = datetime.now(timezone.utc)
        job.adopted_version_id = version.id
        version.adoption_status = AdoptionStatus.PARTIALLY_ADOPTED
        version.is_final = True
        version.teacher_note = note
    else:  # REJECTED
        job.status = AiJobStatus.REJECTED
        job.adopted_by = actor.id
        job.adopted_at = datetime.now(timezone.utc)
        version.adoption_status = AdoptionStatus.REJECTED
        version.teacher_note = note
    _commit(db)
    db.refresh(job)
    return job


# ── 局部重生成 ───────────────────────────────────────────────
def regenerate_job(
    db: Session,
    actor: User,
    job_id: str,
    *,
    base_version_id: str | None = None,
    note: str | None = None,
) -> AiOutputVersion:
    """基于已有任务创建新版本（验收标准 5：局部重生成）。

    任务必须处于 succeeded/reviewed/adopted 才能重生成。
    """
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_manage_job(db, actor, job)
    if job.status not in {AiJobStatus.SUCCEEDED, AiJobStatus.REVIEWED, AiJobStatus.ADOPTED}:
        raise AppException(
            code=40901,
            message=f"任务当前状态「{job.status.value}」不可重生成",
            status_code=409,
        )
    base = None
    if base_version_id:
        base = repository.get_version(db, base_version_id)
        if not base or base.job_id != job.id:
            raise AppException(code=40401, message="基准版本不存在", status_code=404)
    provider = repository.get_active_provider(db)
    if not provider:
        raise AppException(
            code=50001, message="AI Provider 不可用，无法重生成", status_code=500
        )
    context = job.input_summary or build_project_context(db, job.project_id)
    prompt = _build_prompt(job.scene, context, job.output_type)
    if note:
        prompt += f"\n教师重生成要求：{note}"
    content = _call_provider(provider, prompt)
    content_type = _content_type_for_scene(job.scene)
    version = AiOutputVersion(
        job_id=job.id,
        version=repository.next_version_number(db, job.id),
        content=content,
        content_type=content_type,
        schema_status=SchemaStatus.PENDING,
        regenerated_from=base.id if base else None,
        teacher_note=note,
    )
    repository.create_version(db, version)
    drafts, schema_valid = quality_rules.validate_output(
        db, job.project_id, content, content_type
    )
    version.schema_status = SchemaStatus.VALID if schema_valid else SchemaStatus.INVALID
    if not schema_valid:
        version.schema_errors = [d.message for d in drafts]
    _persist_issue_drafts(db, drafts, job_id=job.id, version_id=version.id)
    _commit(db)
    db.refresh(version)
    return version


# ── 质量问题处理 ─────────────────────────────────────────────
def resolve_issue(
    db: Session,
    actor: User,
    issue_id: str,
    resolution: str,
    status: IssueStatus = IssueStatus.RESOLVED,
) -> QualityIssue:
    issue = repository.get_issue(db, issue_id)
    if not issue:
        raise AppException(code=40401, message="质量问题不存在", status_code=404)
    if issue.job_id:
        job = repository.get_job(db, issue.job_id)
        if job:
            policy.ensure_can_manage_job(db, actor, job)
    issue.resolution = resolution
    issue.status = status
    issue.resolved_by = actor.id
    issue.resolved_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(issue)
    return issue


# ── 查询 ─────────────────────────────────────────────────────
def list_jobs(
    db: Session,
    actor: User,
    *,
    project_id: str | None = None,
    scene: AiJobScene | None = None,
    status: AiJobStatus | None = None,
) -> list[AiJob]:
    if project_id:
        policy.ensure_can_create_job(db, actor, project_id)
    jobs = repository.list_jobs(
        db, project_id=project_id, scene=scene, status=status, initiated_by=None
    )
    # 权限过滤：仅返回 actor 可读的项目任务
    result = []
    for job in jobs:
        try:
            policy.ensure_can_read_job(db, actor, job)
            result.append(job)
        except AppException:
            continue
    return result


def get_job_detail(db: Session, actor: User, job_id: str) -> dict:
    job = repository.get_job(db, job_id)
    if not job:
        raise AppException(code=40401, message="AI 任务不存在", status_code=404)
    policy.ensure_can_read_job(db, actor, job)
    versions = repository.list_versions_by_job(db, job_id)
    issues = repository.list_issues_by_job(db, job_id)
    open_blockers = repository.count_open_blockers(db, job_id)
    return {
        "job": job_dict(job),
        "versions": [version_dict(v) for v in versions],
        "issues": [issue_dict(i) for i in issues],
        "open_blockers": open_blockers,
    }


# ── 序列化辅助 ───────────────────────────────────────────────
def job_dict(job: AiJob) -> dict:
    return {
        "id": job.id,
        "project_id": job.project_id,
        "scene": _enum_value(job.scene),
        "status": _enum_value(job.status),
        "output_type": job.output_type,
        "provider_id": job.provider_id,
        "provider_model": job.provider_model,
        "prompt_version": job.prompt_version,
        "input_summary": job.input_summary,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "duration_ms": job.duration_ms,
        "initiated_by": job.initiated_by,
        "task_id": job.task_id,
        "submission_id": job.submission_id,
        "reviewed_by": job.reviewed_by,
        "reviewed_at": job.reviewed_at,
        "adopted_by": job.adopted_by,
        "adopted_at": job.adopted_at,
        "adopted_version_id": job.adopted_version_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def version_dict(version: AiOutputVersion) -> dict:
    return {
        "id": version.id,
        "job_id": version.job_id,
        "version": version.version,
        "content": version.content,
        "content_type": version.content_type,
        "schema_status": _enum_value(version.schema_status),
        "schema_errors": version.schema_errors,
        "adoption_status": _enum_value(version.adoption_status),
        "is_final": version.is_final,
        "teacher_note": version.teacher_note,
        "regenerated_from": version.regenerated_from,
        "created_at": version.created_at,
    }


def issue_dict(issue: QualityIssue) -> dict:
    return {
        "id": issue.id,
        "job_id": issue.job_id,
        "version_id": issue.version_id,
        "severity": _enum_value(issue.severity),
        "rule_code": _enum_value(issue.rule_code),
        "object_ref": issue.object_ref,
        "message": issue.message,
        "status": _enum_value(issue.status),
        "resolution": issue.resolution,
        "resolved_by": issue.resolved_by,
        "resolved_at": issue.resolved_at,
        "created_at": issue.created_at,
    }
