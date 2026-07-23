"""add ai job governance

新增 AI 治理领域表（ai_jobs / ai_output_versions / quality_issues），
为所有 AI 内容生成提供统一的任务状态机、输出版本、质量校验与教师审核。

依据核心闭环实施计划 Task 5：
- AI 任务状态机：created -> queued -> running -> succeeded/failed
  -> reviewed -> adopted/rejected；非法跃迁返回 HTTP 409。
- 每次生成产出 AiOutputVersion，支持局部重生成与版本对比。
- QualityIssue 分阻断/警告/建议三级；阻断问题未处理不能标记正式版本。
- 原始 AI 输出、教师修改、采用状态和最终版本完整留存。

注意：SQLAlchemy SAEnum 默认按枚举 *name* 存储，故 server_default 必须使用 name。

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── AI 任务表 ──────────────────────────────────────────────
    op.create_table(
        'ai_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='所属项目 ID'),
        sa.Column('scene', sa.String(length=20), nullable=False, comment='AI 任务场景枚举 name: LESSON_PLAN/PAPER/RUBRIC/TASK_SHEET/QUESTION/GRADING'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='CREATED', comment='任务状态机枚举 name'),
        sa.Column('output_type', sa.String(length=32), nullable=False, comment='输出类型：教学设计/教案/PPT大纲/任务单/量规/题目'),
        sa.Column('provider_id', sa.String(length=36), nullable=True, comment='调用的 Provider ID'),
        sa.Column('provider_model', sa.String(length=100), nullable=True, comment='调用时使用的模型名快照'),
        sa.Column('prompt_version', sa.String(length=64), nullable=True, comment='提示词版本'),
        sa.Column('input_summary', sa.JSON(), nullable=True, comment='结构化输入摘要'),
        sa.Column('error_code', sa.String(length=32), nullable=True, comment='失败原因码 AiErrorCode name'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='失败详情'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Provider 调用耗时（毫秒）'),
        sa.Column('initiated_by', sa.String(length=36), nullable=False, comment='发起教师 ID'),
        sa.Column('task_id', sa.String(length=36), nullable=True, comment='grading 场景关联任务'),
        sa.Column('submission_id', sa.String(length=36), nullable=True, comment='grading 场景关联提交'),
        sa.Column('reviewed_by', sa.String(length=36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('adopted_by', sa.String(length=36), nullable=True),
        sa.Column('adopted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('adopted_version_id', sa.String(length=36), nullable=True, comment='教师最终采用的输出版本 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['adopted_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_ai_jobs_project_id', 'ai_jobs', ['project_id'], unique=False)
    op.create_index('ix_ai_jobs_status', 'ai_jobs', ['status'], unique=False)
    op.create_index('ix_ai_jobs_initiated_by', 'ai_jobs', ['initiated_by'], unique=False)

    # ── AI 输出版本表 ──────────────────────────────────────────
    op.create_table(
        'ai_output_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False, comment='所属 AI 任务 ID'),
        sa.Column('version', sa.Integer(), nullable=False, comment='版本号（同任务内递增）'),
        sa.Column('content', sa.Text(), nullable=True, comment='原始 AI 输出'),
        sa.Column('content_type', sa.String(length=16), nullable=False, server_default='html', comment='内容类型：html/json/text'),
        sa.Column('schema_status', sa.String(length=16), nullable=False, server_default='PENDING', comment='结构校验状态枚举 name'),
        sa.Column('schema_errors', sa.JSON(), nullable=True, comment='结构校验错误列表'),
        sa.Column('adoption_status', sa.String(length=24), nullable=False, server_default='PENDING', comment='采用状态枚举 name'),
        sa.Column('is_final', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='是否最终版本'),
        sa.Column('teacher_note', sa.Text(), nullable=True, comment='教师审核备注'),
        sa.Column('regenerated_from', sa.String(length=36), nullable=True, comment='局部重生成来源版本 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['ai_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['regenerated_from'], ['ai_output_versions.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_ai_output_versions_job_id', 'ai_output_versions', ['job_id'], unique=False)

    # ── 质量问题表 ─────────────────────────────────────────────
    op.create_table(
        'quality_issues',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=True, comment='关联 AI 任务'),
        sa.Column('version_id', sa.String(length=36), nullable=True, comment='关联输出版本'),
        sa.Column('severity', sa.String(length=16), nullable=False, comment='严重级别枚举 name: BLOCKER/WARNING/SUGGESTION'),
        sa.Column('rule_code', sa.String(length=32), nullable=False, comment='质量规则代码枚举 name'),
        sa.Column('object_ref', sa.String(length=200), nullable=False, comment='问题对象引用'),
        sa.Column('message', sa.Text(), nullable=False, comment='问题描述'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='OPEN', comment='处理状态枚举 name'),
        sa.Column('resolution', sa.Text(), nullable=True, comment='处理说明'),
        sa.Column('resolved_by', sa.String(length=36), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['ai_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['version_id'], ['ai_output_versions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_quality_issues_job_id', 'quality_issues', ['job_id'], unique=False)
    op.create_index('ix_quality_issues_status', 'quality_issues', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_quality_issues_status', table_name='quality_issues')
    op.drop_index('ix_quality_issues_job_id', table_name='quality_issues')
    op.drop_table('quality_issues')

    op.drop_index('ix_ai_output_versions_job_id', table_name='ai_output_versions')
    op.drop_table('ai_output_versions')

    op.drop_index('ix_ai_jobs_initiated_by', table_name='ai_jobs')
    op.drop_index('ix_ai_jobs_status', table_name='ai_jobs')
    op.drop_index('ix_ai_jobs_project_id', table_name='ai_jobs')
    op.drop_table('ai_jobs')
