"""add evaluation improvement domain

新增评价计划领域表（rubrics / rubric_criteria / evidence_artifacts /
evaluation_records / evaluation_scores），并扩展 evaluations 表
（is_legacy）与 submissions 表（review_status 状态机）。

依据核心闭环实施计划 Task 4：
- 旧简单评价（evaluations 表）保留只读，标记 is_legacy=True，显示为"旧版评价记录"。
- 新评价走 evaluation_records，承载状态机与分维度评分。
- submissions.review_status 驱动复核状态机，旧 status 字段镜像兼容。

注意：SQLAlchemy SAEnum 默认按枚举 *name* 存储，故 server_default 必须使用 name。

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 扩展 evaluations 表：is_legacy 标记 ───────────────────
    op.add_column(
        'evaluations',
        sa.Column(
            'is_legacy',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('1'),
            comment='是否旧版简单评价',
        ),
    )

    # ── 扩展 submissions 表：review_status 状态机 ─────────────
    op.add_column(
        'submissions',
        sa.Column(
            'review_status',
            sa.String(length=16),
            nullable=False,
            server_default='SUBMITTED',
            comment='复核状态枚举 name: DRAFT/SUBMITTED/AI_REVIEWED/TEACHER_REVIEWED/RETURNED/RESUBMITTED/FINALIZED',
        ),
    )

    # ── 量规表 ────────────────────────────────────────────────
    op.create_table(
        'rubrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, comment='版本号'),
        sa.Column('is_current', sa.Boolean(), nullable=False, comment='是否当前正式版本'),
        sa.Column('status', sa.String(length=8), nullable=False, comment='量规状态枚举 name: DRAFT/PUBLISHED/ARCHIVED'),
        sa.Column('created_by', sa.String(length=36), nullable=False, comment='创建教师 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_rubrics_project_id', 'rubrics', ['project_id'], unique=False)

    # ── 量规维度表 ────────────────────────────────────────────
    op.create_table(
        'rubric_criteria',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('rubric_id', sa.String(length=36), nullable=False),
        sa.Column('indicator_id', sa.String(length=36), nullable=True, comment='关联指标（可空）'),
        sa.Column('dimension', sa.String(length=200), nullable=False, comment='维度名称'),
        sa.Column('weight', sa.Float(), nullable=False, comment='教师权重 0-1'),
        sa.Column('ai_weight', sa.Float(), nullable=False, comment='AI 权重，默认 0'),
        sa.Column('levels', sa.JSON(), nullable=False, comment='[{level, score, description}]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rubric_id'], ['rubrics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['indicator_id'], ['evaluation_indicators.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_rubric_criteria_rubric_id', 'rubric_criteria', ['rubric_id'], unique=False)

    # ── 证据表 ────────────────────────────────────────────────
    op.create_table(
        'evidence_artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('submission_id', sa.String(length=36), nullable=True, comment='关联提交（可空）'),
        sa.Column('indicator_id', sa.String(length=36), nullable=False, comment='关联指标'),
        sa.Column('plan_id', sa.String(length=36), nullable=True, comment='关联证据计划（可空）'),
        sa.Column('source_type', sa.String(length=12), nullable=False, comment='证据来源类型枚举 name'),
        sa.Column('content_ref', sa.Text(), nullable=False, comment='内容引用'),
        sa.Column('collected_by', sa.String(length=36), nullable=False, comment='采集者 ID'),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False, comment='采集时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['indicator_id'], ['evaluation_indicators.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['evidence_plans.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_evidence_artifacts_project_id', 'evidence_artifacts', ['project_id'], unique=False)
    op.create_index('ix_evidence_artifacts_indicator_id', 'evidence_artifacts', ['indicator_id'], unique=False)

    # ── 评价记录表 ────────────────────────────────────────────
    op.create_table(
        'evaluation_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('task_id', sa.String(length=36), nullable=True, comment='任务级评价时关联任务'),
        sa.Column('student_id', sa.String(length=36), nullable=False, comment='被评学生 ID'),
        sa.Column('evaluator_id', sa.String(length=36), nullable=False, comment='评价者 ID'),
        sa.Column('subject_type', sa.String(length=10), nullable=False, comment='评价主体类型枚举 name'),
        sa.Column('subject_id', sa.String(length=36), nullable=False, comment='主体 ID'),
        sa.Column('source', sa.String(length=8), nullable=False, comment='评价来源枚举 name'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='DRAFT', comment='评价状态机枚举 name'),
        sa.Column('rubric_id', sa.String(length=36), nullable=True, comment='使用的量规版本'),
        sa.Column('total_score', sa.Float(), nullable=True, comment='总分'),
        sa.Column('comment', sa.Text(), nullable=True, comment='总评语'),
        sa.Column('confirmed_by', sa.String(length=36), nullable=True, comment='确认教师 ID'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True, comment='确认时间'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True, comment='发布时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rubric_id'], ['rubrics.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_evaluation_records_project_id', 'evaluation_records', ['project_id'], unique=False)
    op.create_index('ix_evaluation_records_task_id', 'evaluation_records', ['task_id'], unique=False)
    op.create_index('ix_evaluation_records_student_id', 'evaluation_records', ['student_id'], unique=False)

    # ── 分维度评分表 ──────────────────────────────────────────
    op.create_table(
        'evaluation_scores',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('record_id', sa.String(length=36), nullable=False),
        sa.Column('criterion_id', sa.String(length=36), nullable=False, comment='量规维度 ID'),
        sa.Column('suggested_score', sa.Float(), nullable=True, comment='AI 建议分数'),
        sa.Column('final_score', sa.Float(), nullable=True, comment='教师最终分数'),
        sa.Column('evidence_ref', sa.Text(), nullable=True, comment='证据引用'),
        sa.Column('ai_confidence', sa.Float(), nullable=True, comment='AI 置信度 0-1'),
        sa.Column('difference_reason', sa.Text(), nullable=True, comment='人机差异原因'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['record_id'], ['evaluation_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['criterion_id'], ['rubric_criteria.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_evaluation_scores_record_id', 'evaluation_scores', ['record_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_evaluation_scores_record_id', table_name='evaluation_scores')
    op.drop_table('evaluation_scores')

    op.drop_index('ix_evaluation_records_student_id', table_name='evaluation_records')
    op.drop_index('ix_evaluation_records_task_id', table_name='evaluation_records')
    op.drop_index('ix_evaluation_records_project_id', table_name='evaluation_records')
    op.drop_table('evaluation_records')

    op.drop_index('ix_evidence_artifacts_indicator_id', table_name='evidence_artifacts')
    op.drop_index('ix_evidence_artifacts_project_id', table_name='evidence_artifacts')
    op.drop_table('evidence_artifacts')

    op.drop_index('ix_rubric_criteria_rubric_id', table_name='rubric_criteria')
    op.drop_table('rubric_criteria')

    op.drop_index('ix_rubrics_project_id', table_name='rubrics')
    op.drop_table('rubrics')

    op.drop_column('submissions', 'review_status')
    op.drop_column('evaluations', 'is_legacy')
