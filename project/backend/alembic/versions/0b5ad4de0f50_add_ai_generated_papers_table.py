"""add_ai_generated_papers_table

Revision ID: 0b5ad4de0f50
Revises: b27c468c34f2
Create Date: 2026-06-03 22:20:04.616891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b5ad4de0f50'
down_revision: Union[str, Sequence[str], None] = 'b27c468c34f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_generated_papers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False, comment='创建教师ID'),
        sa.Column('template_id', sa.String(length=36), nullable=True, comment='使用的模板ID'),
        sa.Column('subject', sa.String(length=50), nullable=False, comment='学科'),
        sa.Column('grade', sa.String(length=20), nullable=False, comment='年级'),
        sa.Column('title', sa.String(length=200), nullable=False, comment='试卷标题'),
        sa.Column('difficulty', sa.String(length=20), nullable=False, comment='难度'),
        sa.Column('knowledge_points', sa.Text(), nullable=True, comment='知识点(JSON)'),
        sa.Column('questions', sa.Text(), nullable=True, comment='题目列表(JSON)'),
        sa.Column('total_score', sa.Float(), default=100.0),
        sa.Column('duration', sa.Integer(), default=90, comment='建议时长(分钟)'),
        sa.Column('status', sa.String(length=20), default='draft', comment='状态'),
        sa.Column('exported_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('ai_generated_papers')
