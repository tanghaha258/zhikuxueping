"""add rebuild context domain

依据全项目重构计划 Task 2 / M1：
- 新增四张表：project_stage_progress、tool_context_links、
  project_learning_insights、migration_ledger。
- 扩展 ai_jobs：新增 context_mode / project_phase 列，并将 project_id 调整为可空，
  服务层校验项目模式必须有 project_id（独立模式允许为空）。

设计约定：
- 所有新表与列均为增量扩展，不修改历史表结构或数据语义。
- SQLite 测试与 PostgreSQL 生产均需可用：DateTime server_default 使用
  CURRENT_TIMESTAMP（SQLite/PostgreSQL 通用），JSON 列使用 sa.JSON()。
- ai_jobs.project_id 可空变更使用 batch_alter_table，兼容 SQLite 不支持
  ALTER COLUMN 的限制；batch 模式会自动保留既有索引与外键。
- migration_ledger 通过 (source_table, source_id) 唯一约束保证幂等。
- downgrade 移除新增表与列，恢复 project_id 为 NOT NULL；若升级后写入了
  project_id 为空的行，需先回填或清理才能降级（由集成会话在副本库演练）。

Revision ID: h1a2b3c4d5e6
Revises: g8b9c0d1e2f3
Create Date: 2026-07-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'g8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: 新增四张表 + 扩展 ai_jobs。"""

    # ── 项目阶段进度 ─────────────────────────────────────────
    op.create_table(
        'project_stage_progress',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column(
            'phase',
            sa.String(length=32),
            nullable=False,
            comment='项目阶段: diagnosis/design/preparation/implementation/evaluation/improvement/closure',
        ),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            comment='阶段状态: not_started/in_progress/completed/blocked',
        ),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='阶段完成时间'),
        sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True, comment='阶段重新开放时间'),
        sa.Column('reopened_by', sa.String(length=36), nullable=True, comment='重新开放操作人 ID'),
        sa.Column('reopen_reason', sa.Text(), nullable=True, comment='重新开放原因'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id', 'phase', name='uq_project_stage_progress_project_phase'),
    )
    op.create_index(
        'ix_project_stage_progress_project_id',
        'project_stage_progress',
        ['project_id'],
        unique=False,
    )

    # ── 工具上下文链接 ───────────────────────────────────────
    op.create_table(
        'tool_context_links',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column(
            'artifact_type',
            sa.String(length=30),
            nullable=False,
            comment='资产类型: lesson_plan/resource/paper/ai_output/question_bank等',
        ),
        sa.Column('artifact_id', sa.String(length=36), nullable=False, comment='资产 ID'),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='关联项目 ID'),
        sa.Column(
            'phase',
            sa.String(length=32),
            nullable=True,
            comment='项目阶段: diagnosis/design/preparation/implementation/evaluation/improvement/closure',
        ),
        sa.Column(
            'placement',
            sa.String(length=30),
            nullable=False,
            comment='放置位置: pre_test/in_class/post_test/resource/lesson_plan/ai_draft等',
        ),
        sa.Column('task_id', sa.String(length=36), nullable=True, comment='关联任务 ID（可选）'),
        sa.Column('goal_id', sa.String(length=36), nullable=True, comment='关联学习目标 ID（可选）'),
        sa.Column('indicator_id', sa.String(length=36), nullable=True, comment='关联评价指标 ID（可选）'),
        sa.Column('context_snapshot', sa.JSON(), nullable=True, comment='关联时刻的结构化上下文快照'),
        sa.Column('created_by', sa.String(length=36), nullable=True, comment='创建链接的教师 ID'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['goal_id'], ['learning_goals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['indicator_id'], ['evaluation_indicators.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint(
            'artifact_type',
            'artifact_id',
            'project_id',
            'placement',
            name='uq_tool_context_links_artifact_placement',
        ),
    )
    op.create_index(
        'ix_tool_context_links_project_id',
        'tool_context_links',
        ['project_id'],
        unique=False,
    )
    op.create_index(
        'ix_tool_context_links_task_id',
        'tool_context_links',
        ['task_id'],
        unique=False,
    )

    # ── 项目学情诊断快照 ─────────────────────────────────────
    op.create_table(
        'project_learning_insights',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='所属项目 ID'),
        sa.Column('class_id', sa.String(length=36), nullable=True, comment='诊断班级 ID'),
        sa.Column('snapshot', sa.JSON(), nullable=True, comment='诊断快照: 班级画像/薄弱点/分层建议'),
        sa.Column(
            'source_counts',
            sa.JSON(),
            nullable=True,
            comment='数据来源计数: pre_test/submissions/evaluations/question_answers',
        ),
        sa.Column(
            'evidence_cutoff',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='诊断所依据证据的截止时间',
        ),
        sa.Column(
            'status',
            sa.String(length=24),
            nullable=False,
            comment='诊断状态: draft/insufficient_evidence/confirmed/stale',
        ),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True, comment='诊断生成时间'),
        sa.Column('generated_by', sa.String(length=36), nullable=True, comment='生成者 ID'),
        sa.Column('confirmed_by', sa.String(length=36), nullable=True, comment='确认诊断的教师 ID'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True, comment='教师确认时间'),
        sa.Column('teacher_note', sa.Text(), nullable=True, comment='教师人工诊断备注'),
        sa.Column('is_current', sa.Boolean(), nullable=False, comment='是否当前正式快照'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['confirmed_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index(
        'ix_project_learning_insights_project_id',
        'project_learning_insights',
        ['project_id'],
        unique=False,
    )
    op.create_index(
        'ix_project_learning_insights_class_id',
        'project_learning_insights',
        ['class_id'],
        unique=False,
    )

    # ── 数据迁移幂等记录 ─────────────────────────────────────
    op.create_table(
        'migration_ledger',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('batch_id', sa.String(length=36), nullable=False, comment='迁移批次 ID'),
        sa.Column('source_table', sa.String(length=64), nullable=False, comment='源表名'),
        sa.Column('source_id', sa.String(length=36), nullable=False, comment='源记录 ID'),
        sa.Column('target_table', sa.String(length=64), nullable=False, comment='目标表名'),
        sa.Column('target_id', sa.String(length=36), nullable=True, comment='目标记录 ID'),
        sa.Column(
            'status',
            sa.String(length=16),
            nullable=False,
            comment='迁移状态: success/failed/skipped',
        ),
        sa.Column('row_count', sa.Integer(), nullable=True, comment='本次迁移影响行数'),
        sa.Column('checksum', sa.String(length=64), nullable=True, comment='校验摘要'),
        sa.Column(
            'verification_summary',
            sa.JSON(),
            nullable=True,
            comment='校验摘要: 数量比对/孤儿外键/跨校异常等',
        ),
        sa.Column(
            'executed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='迁移实际执行时间',
        ),
        sa.Column('executed_by', sa.String(length=36), nullable=True, comment='执行人 ID'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='失败详情'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
            comment='更新时间',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_table', 'source_id', name='uq_migration_ledger_source'),
    )
    op.create_index(
        'ix_migration_ledger_batch_id',
        'migration_ledger',
        ['batch_id'],
        unique=False,
    )

    # ── 扩展 ai_jobs：project_id 可空 + 新增上下文列 ─────────
    # batch_alter_table 兼容 SQLite（不支持 ALTER COLUMN），
    # 自动保留既有索引（ix_ai_jobs_project_id）与外键（projects.id CASCADE）。
    with op.batch_alter_table('ai_jobs', schema=None) as batch_op:
        batch_op.alter_column(
            'project_id',
            existing_type=sa.String(length=36),
            nullable=True,
            comment='所属项目 ID（独立模式为空，项目模式必填，由服务层校验）',
        )
        batch_op.add_column(
            sa.Column(
                'context_mode',
                sa.String(length=20),
                nullable=True,
                comment='工具上下文模式: INDEPENDENT/PROJECT',
            )
        )
        batch_op.add_column(
            sa.Column(
                'project_phase',
                sa.String(length=32),
                nullable=True,
                comment='项目阶段（项目模式时标记 AI 产出的阶段位置）',
            )
        )


def downgrade() -> None:
    """Downgrade schema: 移除新增表与列，恢复 project_id 为 NOT NULL。

    降级顺序与升级相反：先恢复 ai_jobs，再按依赖逆序删表。
    若升级后写入了 project_id 为空的 ai_jobs 行，需先回填或清理才能降级。
    """
    # ── 恢复 ai_jobs ─────────────────────────────────────────
    with op.batch_alter_table('ai_jobs', schema=None) as batch_op:
        batch_op.drop_column('project_phase')
        batch_op.drop_column('context_mode')
        batch_op.alter_column(
            'project_id',
            existing_type=sa.String(length=36),
            nullable=False,
            comment='所属项目 ID（grading 场景也关联项目）',
        )

    # ── 删 migration_ledger ──────────────────────────────────
    op.drop_index('ix_migration_ledger_batch_id', table_name='migration_ledger')
    op.drop_table('migration_ledger')

    # ── 删 project_learning_insights ─────────────────────────
    op.drop_index('ix_project_learning_insights_class_id', table_name='project_learning_insights')
    op.drop_index('ix_project_learning_insights_project_id', table_name='project_learning_insights')
    op.drop_table('project_learning_insights')

    # ── 删 tool_context_links ────────────────────────────────
    op.drop_index('ix_tool_context_links_task_id', table_name='tool_context_links')
    op.drop_index('ix_tool_context_links_project_id', table_name='tool_context_links')
    op.drop_table('tool_context_links')

    # ── 删 project_stage_progress ────────────────────────────
    op.drop_index('ix_project_stage_progress_project_id', table_name='project_stage_progress')
    op.drop_table('project_stage_progress')
