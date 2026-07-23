"""add project design domain

扩展 projects 表（project_type/core_subject_id/review_status/data_origin）
并新增项目设计领域 5 张表：project_problems、subject_contributions、
learning_goals、evaluation_indicators、evidence_plans。

依据核心闭环实施计划 Task 1：
- 现有项目全部保留为草稿（review_status 默认 draft），不伪造新字段。
- 新增列除 review_status 外均为可空，避免历史数据被强制赋值。
- SQLite 将 sa.Enum 存为 VARCHAR 且无 CHECK 约束，status 列宽度已可容纳
  pending_review（14 字符），故无需变更 status 列类型即可支持新枚举值。

Revision ID: f1a2b3c4d5e6
Revises: e3a1b2c4d5e6
Create Date: 2026-07-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e3a1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 扩展 projects 表 ─────────────────────────────────────
    # project_type: 历史项目为 NULL（未知类型），不伪造。
    op.add_column(
        'projects',
        sa.Column('project_type', sa.String(length=30), nullable=True, comment='项目类型，如 cross_subject'),
    )
    # core_subject_id: 历史项目为 NULL，未设置前无法进入正式状态。
    op.add_column(
        'projects',
        sa.Column('core_subject_id', sa.String(length=36), nullable=True, comment='唯一核心学科 ID'),
    )
    # review_status: 设计/内容审核状态，独立于生命周期 status。
    # NOT NULL + server_default='DRAFT' 保证历史行得到草稿值，不伪造审核结果。
    # 注意：SQLAlchemy 的 SAEnum(ReviewStatus) 默认按枚举 *name* 存储（与 status 列
    # 存储 'ACTIVE' 一致），故 server_default 必须使用 name 'DRAFT' 而非 value 'draft'，
    # 否则历史行加载时会因 LookupError 而失败。
    op.add_column(
        'projects',
        sa.Column(
            'review_status',
            sa.String(length=14),
            nullable=False,
            server_default='DRAFT',
            comment='审核状态枚举 name: DRAFT/PENDING_REVIEW/APPROVED/RETURNED/PUBLISHED/ARCHIVED',
        ),
    )
    # data_origin: 数据来源标识，历史项目为 NULL（未知来源）。
    op.add_column(
        'projects',
        sa.Column(
            'data_origin',
            sa.String(length=8),
            nullable=True,
            comment='数据来源: real/test/demo/imported',
        ),
    )

    # ── 项目真实问题（版本化，一个项目一条 is_current=True）─────
    op.create_table(
        'project_problems',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('context', sa.Text(), nullable=False, comment='情境描述'),
        sa.Column('object', sa.Text(), nullable=True, comment='问题对象'),
        sa.Column('audience', sa.Text(), nullable=True, comment='真实受众'),
        sa.Column('constraints', sa.Text(), nullable=True, comment='约束条件'),
        sa.Column('deliverable', sa.Text(), nullable=True, comment='最终成果'),
        sa.Column('usage', sa.Text(), nullable=True, comment='成果用途'),
        sa.Column('is_current', sa.Boolean(), nullable=False, comment='是否当前正式版本'),
        sa.Column('version', sa.Integer(), nullable=False, comment='版本号'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_problems_project_id', 'project_problems', ['project_id'], unique=False)

    # ── 学科贡献（核心/支撑）─────────────────────────────────
    op.create_table(
        'subject_contributions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('subject_id', sa.String(length=36), nullable=False, comment='学科 ID'),
        sa.Column('role', sa.String(length=7), nullable=False, comment='学科角色: core/support'),
        sa.Column('knowledge', sa.Text(), nullable=True, comment='知识贡献'),
        sa.Column('thinking', sa.Text(), nullable=True, comment='思维方式贡献'),
        sa.Column('inquiry', sa.Text(), nullable=True, comment='探究方法贡献'),
        sa.Column('removal_impact', sa.Text(), nullable=True, comment='移除该学科对项目的影响'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_subject_contributions_project_id', 'subject_contributions', ['project_id'], unique=False)

    # ── 学习目标 ─────────────────────────────────────────────
    op.create_table(
        'learning_goals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('goal_type', sa.String(length=15), nullable=False, comment='目标类型: knowledge/ability/transfer/collaboration/practice'),
        sa.Column('name', sa.String(length=200), nullable=False, comment='目标名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='目标描述'),
        sa.Column('scope', sa.String(length=100), nullable=True, comment='目标范围'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_learning_goals_project_id', 'learning_goals', ['project_id'], unique=False)

    # ── 评价指标（绑定学习目标）──────────────────────────────
    op.create_table(
        'evaluation_indicators',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('goal_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('observable_behavior', sa.Text(), nullable=False, comment='可观察行为描述'),
        sa.Column('level_rule', sa.Text(), nullable=True, comment='等级判定规则'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['goal_id'], ['learning_goals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_evaluation_indicators_goal_id', 'evaluation_indicators', ['goal_id'], unique=False)
    op.create_index('ix_evaluation_indicators_project_id', 'evaluation_indicators', ['project_id'], unique=False)

    # ── 证据计划（绑定指标 + 教学阶段）────────────────────────
    op.create_table(
        'evidence_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('indicator_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('stage', sa.String(length=10), nullable=False, comment='教学阶段: pre_class/in_class/post_class'),
        sa.Column('evidence_type', sa.String(length=15), nullable=False, comment='证据类型: artifact/observation/test/reflection/process_log'),
        sa.Column('collector', sa.String(length=10), nullable=False, comment='采集者: teacher/student/peer/system'),
        sa.Column('required', sa.Boolean(), nullable=False, comment='是否必须采集'),
        sa.Column('description', sa.Text(), nullable=True, comment='采集说明'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False, comment='更新时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['indicator_id'], ['evaluation_indicators.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_evidence_plans_indicator_id', 'evidence_plans', ['indicator_id'], unique=False)
    op.create_index('ix_evidence_plans_project_id', 'evidence_plans', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    降级顺序与升级相反：先删子表（证据计划、指标、目标、贡献、问题），
    再删 projects 扩展列。历史项目行保留，仅移除新增列与表。
    """
    op.drop_index('ix_evidence_plans_project_id', table_name='evidence_plans')
    op.drop_index('ix_evidence_plans_indicator_id', table_name='evidence_plans')
    op.drop_table('evidence_plans')

    op.drop_index('ix_evaluation_indicators_project_id', table_name='evaluation_indicators')
    op.drop_index('ix_evaluation_indicators_goal_id', table_name='evaluation_indicators')
    op.drop_table('evaluation_indicators')

    op.drop_index('ix_learning_goals_project_id', table_name='learning_goals')
    op.drop_table('learning_goals')

    op.drop_index('ix_subject_contributions_project_id', table_name='subject_contributions')
    op.drop_table('subject_contributions')

    op.drop_index('ix_project_problems_project_id', table_name='project_problems')
    op.drop_table('project_problems')

    op.drop_column('projects', 'data_origin')
    op.drop_column('projects', 'review_status')
    op.drop_column('projects', 'core_subject_id')
    op.drop_column('projects', 'project_type')
