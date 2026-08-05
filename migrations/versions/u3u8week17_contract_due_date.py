"""تاريخ استحقاق التحصيل على العقود

Revision ID: u3u8week17_contract_due
Revises: t2t7week16cust_nat_addr
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'u3u8week17_contract_due'
down_revision = 't2t7week16cust_nat_addr'
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
    if _has_column(bind, 'contracts', 'due_date'):
        return
    with op.batch_alter_table('contracts') as batch_op:
        batch_op.add_column(sa.Column('due_date', sa.Date(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'contracts', 'due_date'):
        return
    with op.batch_alter_table('contracts') as batch_op:
        batch_op.drop_column('due_date')
