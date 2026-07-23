"""add submissions improvements operational

新增提交订正版本、学情改进与二次评价、运营证据领域表：
- submission_revisions：提交订正版本（Task 6）
- improvement_suggestions / improvement_tasks / second_evaluations：学情改进与二次评价（Task 7）
- operational_metrics / evidence_ledger / export_records：运营证据（Task 8）

依据核心闭环实施计划 Task 6/7/8：
- 提交订正版本支撑订正状态机、幂等提交键、二次评价入口。
- 学情改进领域：建议必须引用评价证据；改进任务可追溯到原评价与二次评价；
  二次评价记录前后分数差与对比摘要。
- 运营证据领域：对外指标含公式/周期/样本量/来源/责任人；导出落审计且需二次确认。

注意：SQLAlchemy SAEnum 默认按枚举 *name* 存储，故 server_default 必须使用 name。

Revision ID: f7a8b9c0d1e2
Revises: c5d6e7f8a9b0
Create Date: 2026-07-23 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 提交订正版本表（Task 6）────────────────────────────────
    op.create_table(
        'submission_revisions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('submission_id', sa.String(length=36), nullable=False, comment='所属提交线程 ID'),
        sa.Column('attempt_number', sa.Integer(), nullable=False, comment='尝试序号（同一线程内递增）'),
        sa.Column('content', sa.Text(), nullable=True, comment='作答内容'),
        sa.Column('file_urls', sa.JSON(), nullable=True, comment='附件 URL 列表'),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True, comment='客户端幂等键，重复提交不生成新版本'),
        sa.Column('review_status', sa.String(length=16), nullable=False, comment='该版本创建时的复核状态枚举 name'),
        sa.Column('teacher_comment', sa.Text(), nullable=True, comment='教师该轮反馈（学生可见）'),
        sa.Column('teacher_private_note', sa.Text(), nullable=True, comment='教师私有备注（学生不可见）'),
        sa.Column('reassess_reason', sa.Text(), nullable=True, comment='学生发起二次评价的理由'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True, comment='提交时间'),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True, comment='教师复核时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('idempotency_key', name='uq_submission_revisions_idempotency_key'),
    )
    op.create_index('ix_submission_revisions_submission_id', 'submission_revisions', ['submission_id'], unique=False)
    op.create_index('ix_submission_revisions_idempotency_key', 'submission_revisions', ['idempotency_key'], unique=False)

    # ── 改进建议表（Task 7）────────────────────────────────────
    op.create_table(
        'improvement_suggestions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='所属项目 ID'),
        sa.Column('student_id', sa.String(length=36), nullable=True, comment='被建议学生 ID（班级共性建议可空）'),
        sa.Column('created_from_evaluation_id', sa.String(length=36), nullable=False, comment='来源评价记录 ID（验收：建议必须引用评价证据）'),
        sa.Column('evidence_reference', sa.Text(), nullable=False, comment='证据引用：EvaluationScore/Artifact/AiJob ID 等可追溯位置'),
        sa.Column('title', sa.String(length=200), nullable=False, comment='建议标题'),
        sa.Column('description', sa.Text(), nullable=False, comment='建议描述'),
        sa.Column('status', sa.String(length=8), nullable=False, server_default='DRAFT', comment='建议状态机枚举 name: DRAFT/ADOPTED/MODIFIED/REJECTED'),
        sa.Column('decision_reason', sa.Text(), nullable=True, comment='采用/修改/拒绝原因留痕'),
        sa.Column('modified_description', sa.Text(), nullable=True, comment='教师修改后的建议描述（modified 状态时使用）'),
        sa.Column('decided_by', sa.String(length=36), nullable=True, comment='决定教师 ID'),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True, comment='决定时间'),
        sa.Column('created_by', sa.String(length=36), nullable=False, comment='创建教师 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_improvement_suggestions_project_id', 'improvement_suggestions', ['project_id'], unique=False)
    op.create_index('ix_improvement_suggestions_student_id', 'improvement_suggestions', ['student_id'], unique=False)

    # ── 改进任务表（Task 7）────────────────────────────────────
    op.create_table(
        'improvement_tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='所属项目 ID'),
        sa.Column('link_suggestion_id', sa.String(length=36), nullable=True, comment='关联建议 ID（可空：教师可直接创建改进任务）'),
        sa.Column('original_task_id', sa.String(length=36), nullable=True, comment='原任务 ID（用于追溯到首次评价对应的任务）'),
        sa.Column('created_from_evaluation_id', sa.String(length=36), nullable=False, comment='来源评价记录 ID（验收：改进任务可追溯到原评价）'),
        sa.Column('task_type', sa.String(length=32), nullable=False, comment='改进任务类型枚举 name: foundation_consolidation/enhancement_application/extension_transfer/second_evaluation'),
        sa.Column('title', sa.String(length=200), nullable=False, comment='任务标题'),
        sa.Column('description', sa.Text(), nullable=False, comment='任务描述'),
        sa.Column('generated_task_id', sa.String(length=36), nullable=True, comment='生成的正式任务 ID（若已发布给学生）'),
        sa.Column('created_by', sa.String(length=36), nullable=False, comment='创建教师 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['link_suggestion_id'], ['improvement_suggestions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['original_task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['generated_task_id'], ['tasks.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_improvement_tasks_project_id', 'improvement_tasks', ['project_id'], unique=False)

    # ── 二次评价表（Task 7）────────────────────────────────────
    op.create_table(
        'second_evaluations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False, comment='所属项目 ID'),
        sa.Column('student_id', sa.String(length=36), nullable=False, comment='被评学生 ID'),
        sa.Column('first_evaluation_id', sa.String(length=36), nullable=False, comment='首次评价记录 ID（EvaluationRecord.id）'),
        sa.Column('second_evaluation_id', sa.String(length=36), nullable=False, comment='第二次评价记录 ID（EvaluationRecord.id）'),
        sa.Column('link_suggestion_id', sa.String(length=36), nullable=True, comment='关联建议 ID（可空）'),
        sa.Column('link_improvement_task_id', sa.String(length=36), nullable=True, comment='关联改进任务 ID（可空）'),
        sa.Column('comparison_summary', sa.Text(), nullable=True, comment='前后对比摘要：分数差/达成度变化/证据引用'),
        sa.Column('first_score', sa.Float(), nullable=True, comment='首次评价总分快照'),
        sa.Column('second_score', sa.Float(), nullable=True, comment='第二次评价总分快照'),
        sa.Column('created_by', sa.String(length=36), nullable=False, comment='创建教师 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['link_suggestion_id'], ['improvement_suggestions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['link_improvement_task_id'], ['improvement_tasks.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_second_evaluations_project_id', 'second_evaluations', ['project_id'], unique=False)
    op.create_index('ix_second_evaluations_student_id', 'second_evaluations', ['student_id'], unique=False)

    # ── 运营指标表（Task 8）────────────────────────────────────
    op.create_table(
        'operational_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False, comment='指标名称'),
        sa.Column('code', sa.String(length=64), nullable=False, comment='指标代码（唯一，便于引用与导出对照）'),
        sa.Column('formula', sa.Text(), nullable=False, comment='指标公式或计算口径，对外可见（验收 3.8.3）'),
        sa.Column('period', sa.String(length=20), nullable=False, server_default='MONTHLY', comment='统计周期枚举 name: DAILY/WEEKLY/MONTHLY/QUARTERLY/ANNUAL/AD_HOC'),
        sa.Column('sample_size', sa.Integer(), nullable=True, comment='样本量（数据条数）'),
        sa.Column('source_table', sa.String(length=120), nullable=True, comment='来源表或数据集名称'),
        sa.Column('source_owner', sa.String(length=120), nullable=True, comment='数据来源责任方（系统/部门/录入人）'),
        sa.Column('responsible_person', sa.String(length=120), nullable=True, comment='指标责任人'),
        sa.Column('data_origin', sa.String(length=8), nullable=False, server_default='REAL', comment='数据来源枚举 name：real/test/demo/imported'),
        sa.Column('value', sa.Float(), nullable=True, comment='指标当前值（不伪造，未采集时为空）'),
        sa.Column('value_collected_at', sa.DateTime(timezone=True), nullable=True, comment='指标值采集时间（无值时为空，不补零）'),
        sa.Column('school_id', sa.String(length=36), nullable=True, comment='所属学校 ID（NULL 表示跨校汇总）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('code', name='uq_operational_metrics_code'),
    )

    # ── 证据台账表（Task 8）────────────────────────────────────
    op.create_table(
        'evidence_ledger',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('metric_id', sa.String(length=36), nullable=False, comment='关联运营指标 ID'),
        sa.Column('evidence_ref', sa.String(length=255), nullable=False, comment='证据引用：表名+主键 / 文件路径 / 外部台账编号'),
        sa.Column('evidence_summary', sa.Text(), nullable=True, comment='证据摘要（脱敏后可见文本）'),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False, comment='证据采集时间'),
        sa.Column('verified_by', sa.String(length=36), nullable=True, comment='核验人 ID（教师/管理员）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['metric_id'], ['operational_metrics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
    )

    # ── 导出审计记录表（Task 8）────────────────────────────────
    op.create_table(
        'export_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('exporter_id', sa.String(length=36), nullable=False, comment='导出操作人 ID'),
        sa.Column('scope_school_id', sa.String(length=36), nullable=True, comment='导出范围学校 ID（NULL 表示跨校，仅系统管理员）'),
        sa.Column('metric_ids', sa.Text(), nullable=True, comment='导出涉及的指标 ID 列表（逗号分隔）'),
        sa.Column('anonymized', sa.Boolean(), nullable=False, server_default=sa.text('1'), comment='是否启用脱敏（学生姓名→学号尾号、教师姓名→工号）'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='PENDING', comment='导出状态机枚举 name: PENDING/PREVIEWED/CONFIRMED/FAILED/REVOKED'),
        sa.Column('audit_note', sa.Text(), nullable=True, comment='导出审计备注'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True, comment='二次确认时间'),
        sa.Column('payload_ref', sa.String(length=255), nullable=True, comment='导出载荷引用（文件路径或快照 ID，预览阶段可空）'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exporter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scope_school_id'], ['schools.id'], ondelete='SET NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('export_records')
    op.drop_table('evidence_ledger')
    op.drop_table('operational_metrics')
    op.drop_table('second_evaluations')
    op.drop_table('improvement_tasks')
    op.drop_table('improvement_suggestions')
    op.drop_index('ix_submission_revisions_idempotency_key', table_name='submission_revisions')
    op.drop_index('ix_submission_revisions_submission_id', table_name='submission_revisions')
    op.drop_table('submission_revisions')
