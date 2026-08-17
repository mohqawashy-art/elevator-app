"""حجم وموضع ختم وتوقيع الشركة

Revision ID: f5f0week27_company_seal_layout
Revises: e4e9week26_company_seal
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'f5f0week27_company_seal_layout'
down_revision = 'e4e9week26_company_seal'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _columns(bind, table: str) -> set[str]:
    if not _has_table(bind, table):
        return set()
    return {column['name'] for column in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    columns = _columns(bind, 'settings')
    if not columns:
        return
    additions = (
        sa.Column('company_stamp_width', sa.Integer(), nullable=True, server_default='110'),
        sa.Column('company_stamp_offset_x', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('company_stamp_offset_y', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('company_sign_width', sa.Integer(), nullable=True, server_default='140'),
        sa.Column('company_sign_offset_x', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('company_sign_offset_y', sa.Integer(), nullable=True, server_default='0'),
    )
    with op.batch_alter_table('settings') as batch_op:
        for column in additions:
            if column.name not in columns:
                batch_op.add_column(column)


def downgrade():
    bind = op.get_bind()
    columns = _columns(bind, 'settings')
    if not columns:
        return
    names = (
        'company_sign_offset_y',
        'company_sign_offset_x',
        'company_sign_width',
        'company_stamp_offset_y',
        'company_stamp_offset_x',
        'company_stamp_width',
    )
    with op.batch_alter_table('settings') as batch_op:
        for name in names:
            if name in columns:
                batch_op.drop_column(name)
