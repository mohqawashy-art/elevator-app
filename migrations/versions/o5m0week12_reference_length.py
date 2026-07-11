"""توسيع عمود reference للإيرادات والمصروفات لاستيعاب أسماء المرفقات

Revision ID: o5m0week12reflen
Revises: n4l9week12phonelen
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'o5m0week12reflen'
down_revision = 'n4l9week12phonelen'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _col_type(bind, table: str, column: str):
    for c in sa.inspect(bind).get_columns(table):
        if c['name'] == column:
            return c.get('type')
    return None


def upgrade():
    bind = op.get_bind()
    for table in ('expenses', 'revenues'):
        if not _has_table(bind, table):
            continue
        if _col_type(bind, table, 'reference') is None:
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                'reference',
                existing_type=sa.String(length=100),
                type_=sa.String(length=500),
                existing_nullable=True,
            )


def downgrade():
    bind = op.get_bind()
    for table in ('expenses', 'revenues'):
        if not _has_table(bind, table):
            continue
        if _col_type(bind, table, 'reference') is None:
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                'reference',
                existing_type=sa.String(length=500),
                type_=sa.String(length=100),
                existing_nullable=True,
            )
