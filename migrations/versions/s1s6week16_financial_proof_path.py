"""إثبات دفع/صرف للإيرادات والمصروفات

Revision ID: s1s6week16_fin_proof
Revises: r0r5week15_tech_profile
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 's1s6week16_fin_proof'
down_revision = 'r0r5week15_tech_profile'
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
    for table in ('revenues', 'expenses'):
        if not _has_table(bind, table):
            continue
        if _has_column(bind, table, 'proof_path'):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('proof_path', sa.String(300), nullable=True))


def downgrade():
    bind = op.get_bind()
    for table in ('revenues', 'expenses'):
        if not _has_table(bind, table):
            continue
        if not _has_column(bind, table, 'proof_path'):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column('proof_path')
