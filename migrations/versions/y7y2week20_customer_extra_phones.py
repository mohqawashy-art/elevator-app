"""أرقام جوال إضافية للعميل (JSON)

Revision ID: y7y2week20cust_phones
Revises: x6x1week19ratelimit
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'y7y2week20cust_phones'
down_revision = 'x6x1week19ratelimit'
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
    if _has_column(bind, 'customers', 'extra_phones'):
        return
    with op.batch_alter_table('customers') as batch_op:
        batch_op.add_column(sa.Column('extra_phones', sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'customers', 'extra_phones'):
        return
    with op.batch_alter_table('customers') as batch_op:
        batch_op.drop_column('extra_phones')
