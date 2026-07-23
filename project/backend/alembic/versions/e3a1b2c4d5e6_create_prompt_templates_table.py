"""create prompt_templates table

Revision ID: e3a1b2c4d5e6
Revises: d9c7e2f1b1d3
Create Date: 2026-06-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3a1b2c4d5e6'
down_revision: Union[str, Sequence[str], None] = '4f5100746ebf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('prompt_templates',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False, comment='模板名称'),
    sa.Column('subject', sa.String(length=50), nullable=False, comment='适用学科'),
    sa.Column('exam_type', sa.String(length=20), nullable=False, server_default='quiz', comment='考试类型'),
    sa.Column('template', sa.Text(), nullable=False, comment='提示词模板内容'),
    sa.Column('description', sa.Text(), nullable=True, comment='模板说明'),
    sa.Column('is_active', sa.Boolean(), server_default='1', comment='是否启用'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('prompt_templates')
