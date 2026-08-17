"""ختم وتوقيع الشركة على المستندات

Revision ID: e4e9week26_company_seal
Revises: d3d8week25_journals
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'e4e9week26_company_seal'
down_revision = 'd3d8week25_journals'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c['name'] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'settings'):
        return
    with op.batch_alter_table('settings') as batch_op:
        if not _has_column(bind, 'settings', 'company_stamp_path'):
            batch_op.add_column(sa.Column('company_stamp_path', sa.String(300), nullable=True))
        if not _has_column(bind, 'settings', 'company_sign_path'):
            batch_op.add_column(sa.Column('company_sign_path', sa.String(300), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'settings'):
        return
    with op.batch_alter_table('settings') as batch_op:
        if _has_column(bind, 'settings', 'company_sign_path'):
            batch_op.drop_column('company_sign_path')
        if _has_column(bind, 'settings', 'company_stamp_path'):
            batch_op.drop_column('company_stamp_path')
