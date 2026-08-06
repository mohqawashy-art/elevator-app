"""من سجّل العملية على الإيرادات والمصروفات

Revision ID: v4v9week17_created_by
Revises: u3u8week17_contract_due
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'v4v9week17_created_by'
down_revision = 'u3u8week17_contract_due'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c['name'] == column for c in sa.inspect(bind).get_columns(table))


def _add_created_by(table: str):
    bind = op.get_bind()
    if not _has_table(bind, table):
        return
    with op.batch_alter_table(table) as batch_op:
        if not _has_column(bind, table, 'created_by_user_id'):
            batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        if not _has_column(bind, table, 'created_by_name'):
            batch_op.add_column(sa.Column('created_by_name', sa.String(length=100), nullable=True))


def _drop_created_by(table: str):
    bind = op.get_bind()
    if not _has_table(bind, table):
        return
    with op.batch_alter_table(table) as batch_op:
        if _has_column(bind, table, 'created_by_name'):
            batch_op.drop_column('created_by_name')
        if _has_column(bind, table, 'created_by_user_id'):
            batch_op.drop_column('created_by_user_id')


def upgrade():
    _add_created_by('revenues')
    _add_created_by('expenses')


def downgrade():
    _drop_created_by('expenses')
    _drop_created_by('revenues')
