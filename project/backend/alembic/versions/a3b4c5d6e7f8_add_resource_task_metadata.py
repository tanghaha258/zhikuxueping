"""add resource task metadata

扩展 resources 表（tier/stage/cognitive_level/reading_level/prerequisites/
review_status/source_type/source_ref/usage_tip）与 tasks 表
（stage/tier/publish_status/submission_type/max_attempts/scheduled_at），
并新增 task_dependencies 表。

依据核心闭环实施计划 Task 3：
- 旧资源保留但标记为未分层草稿：tier/stage 为 NULL，review_status 默认 DRAFT。
- 旧任务保留原状态并映射到兼容状态：publish_status 默认 PUBLISHED（保留对学生可见），
  stage/tier 为 NULL；新任务由 ORM 默认 DRAFT 起步。
- task_dependencies 表达任务链前置->后置有向边，唯一约束避免重复登记。

注意：SQLAlchemy SAEnum 默认按枚举 *name* 存储（与 projects.review_status 一致），
故 server_default 必须使用 name（'DRAFT'/'PUBLISHED'）而非 value。

Revision ID: a3b4c5d6e7f8
Revises: f1a2b3c4d5e6
Create Date: 2026-07-23 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 扩展 resources 表 ─────────────────────────────────────
    op.add_column(
        'resources',
        sa.Column('tier', sa.String(length=10), nullable=True, comment='资源层级: foundation/enhancement/extension'),
    )
    op.add_column(
        'resources',
        sa.Column('stage', sa.String(length=10), nullable=True, comment='教学阶段: pre/in/post_class'),
    )
    op.add_column(
        'resources',
        sa.Column('cognitive_level', sa.String(length=30), nullable=True, comment='认知难度'),
    )
    op.add_column(
        'resources',
        sa.Column('reading_level', sa.String(length=30), nullable=True, comment='阅读难度'),
    )
    op.add_column(
        'resources',
        sa.Column('prerequisites', sa.Text(), nullable=True, comment='前置知识'),
    )
    # review_status: NOT NULL + server_default='DRAFT'（枚举 name），历史资源为草稿。
    op.add_column(
        'resources',
        sa.Column(
            'review_status',
            sa.String(length=14),
            nullable=False,
            server_default='DRAFT',
            comment='审核状态枚举 name: DRAFT/PENDING_REVIEW/APPROVED/RETURNED/PUBLISHED/ARCHIVED',
        ),
    )
    op.add_column(
        'resources',
        sa.Column('source_type', sa.String(length=8), nullable=True, comment='来源类型: manual/ai/imported'),
    )
    op.add_column(
        'resources',
        sa.Column('source_ref', sa.String(length=300), nullable=True, comment='版权/出处'),
    )
    op.add_column(
        'resources',
        sa.Column('usage_tip', sa.Text(), nullable=True, comment='使用建议'),
    )

    # ── 扩展 tasks 表 ─────────────────────────────────────────
    op.add_column(
        'tasks',
        sa.Column('stage', sa.String(length=10), nullable=True, comment='教学阶段: pre/in/post_class'),
    )
    op.add_column(
        'tasks',
        sa.Column('tier', sa.String(length=10), nullable=True, comment='分层对象: foundation/enhancement/extension'),
    )
    # publish_status: NOT NULL + server_default='PUBLISHED'（枚举 name），旧任务保留可见。
    op.add_column(
        'tasks',
        sa.Column(
            'publish_status',
            sa.String(length=12),
            nullable=False,
            server_default='PUBLISHED',
            comment='发布状态枚举 name: DRAFT/SCHEDULED/PUBLISHED/IN_PROGRESS/CLOSED/ARCHIVED',
        ),
    )
    op.add_column(
        'tasks',
        sa.Column('submission_type', sa.String(length=10), nullable=True, comment='提交类型: online/attachment/both/none'),
    )
    op.add_column(
        'tasks',
        sa.Column('max_attempts', sa.Integer(), nullable=True, comment='最大提交次数；NULL 表示不限'),
    )
    op.add_column(
        'tasks',
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True, comment='定时发布时间'),
    )

    # ── 任务依赖表 ────────────────────────────────────────────
    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('predecessor_id', sa.String(length=36), nullable=False, comment='前置任务 ID'),
        sa.Column('successor_id', sa.String(length=36), nullable=False, comment='后置任务 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['predecessor_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['successor_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('predecessor_id', 'successor_id', name='uq_task_dependency_pair'),
    )
    op.create_index('ix_task_dependencies_predecessor_id', 'task_dependencies', ['predecessor_id'], unique=False)
    op.create_index('ix_task_dependencies_successor_id', 'task_dependencies', ['successor_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    降级顺序：先删任务依赖表，再移除 tasks/resources 扩展列。历史行保留。
    """
    op.drop_index('ix_task_dependencies_successor_id', table_name='task_dependencies')
    op.drop_index('ix_task_dependencies_predecessor_id', table_name='task_dependencies')
    op.drop_table('task_dependencies')

    for col in ('scheduled_at', 'max_attempts', 'submission_type', 'publish_status', 'tier', 'stage'):
        op.drop_column('tasks', col)

    for col in ('usage_tip', 'source_ref', 'source_type', 'review_status', 'prerequisites', 'reading_level', 'cognitive_level', 'stage', 'tier'):
        op.drop_column('resources', col)
