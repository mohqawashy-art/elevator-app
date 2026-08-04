"""العنوان الوطني للعميل في الفواتير الضريبية

Revision ID: t2t7week16cust_nat_addr
Revises: s1s6week16_fin_proof
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 't2t7week16cust_nat_addr'
down_revision = 's1s6week16_fin_proof'
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
    if _has_column(bind, 'customers', 'national_address'):
        return
    with op.batch_alter_table('customers') as batch_op:
        batch_op.add_column(sa.Column('national_address', sa.String(length=200), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'customers', 'national_address'):
        return
    with op.batch_alter_table('customers') as batch_op:
        batch_op.drop_column('national_address')
