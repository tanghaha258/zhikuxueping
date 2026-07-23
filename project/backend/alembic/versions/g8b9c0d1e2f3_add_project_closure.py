"""add project closure

扩展 projects 表：教师结项反思、重新开放归档原因/时间/操作人。

依据核心闭环实施计划 Task 9：
- 教师反思（teacher_reflection）：教师对项目结项的反思文本，结项时填写。
- 重新开放留痕（reopen_reason/reopened_at/reopened_by）：归档项目被 school_admin
  重新开放时记录原因与操作人，便于审计追溯（验收：重新开放必须授权并记录原因）。

新增字段均可空，历史项目保持 NULL，不伪造数据。

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-23 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g8b9c0d1e2f3'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 扩展 projects 表：结项/归档字段（Task 9）────────────
    # 教师结项反思文本，结项时由教师填写。
    op.add_column(
        'projects',
        sa.Column('teacher_reflection', sa.Text(), nullable=True, comment='教师结项反思'),
    )
    # 重新开放归档项目的原因留痕（school_admin 填写）。
    op.add_column(
        'projects',
        sa.Column('reopen_reason', sa.Text(), nullable=True, comment='重新开放归档项目的原因'),
    )
    # 重新开放时间。
    op.add_column(
        'projects',
        sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True, comment='重新开放时间'),
    )
    # 重新开放操作人 ID。
    op.add_column(
        'projects',
        sa.Column('reopened_by', sa.String(length=36), nullable=True, comment='重新开放操作人 ID'),
    )


def downgrade() -> None:
    """Downgrade schema.

    降级顺序：按添加的逆序移除字段。历史行保留。
    """
    for col in ('reopened_by', 'reopened_at', 'reopen_reason', 'teacher_reflection'):
        op.drop_column('projects', col)
