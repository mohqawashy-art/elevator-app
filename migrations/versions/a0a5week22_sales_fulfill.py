"""حقول إتمام طلبات المبيعات (إرسال تجربة / عرض سعر)

Revision ID: a0a5week22sales_fulfill
Revises: z9z4week21sales_leads
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'a0a5week22sales_fulfill'
down_revision = 'z9z4week21sales_leads'
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
    if not _has_table(bind, 'sales_leads'):
        return
    with op.batch_alter_table('sales_leads') as batch_op:
        if not _has_column(bind, 'sales_leads', 'fulfilled_at'):
            batch_op.add_column(sa.Column('fulfilled_at', sa.DateTime(), nullable=True))
        if not _has_column(bind, 'sales_leads', 'result_org_id'):
            batch_op.add_column(sa.Column('result_org_id', sa.Integer(), nullable=True))
        if not _has_column(bind, 'sales_leads', 'customer_mail_sent'):
            batch_op.add_column(sa.Column('customer_mail_sent', sa.Boolean(), nullable=True))
        if not _has_column(bind, 'sales_leads', 'action_note'):
            batch_op.add_column(sa.Column('action_note', sa.String(length=500), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'sales_leads'):
        return
    with op.batch_alter_table('sales_leads') as batch_op:
        for name in ('action_note', 'customer_mail_sent', 'result_org_id', 'fulfilled_at'):
            if _has_column(bind, 'sales_leads', name):
                batch_op.drop_column(name)
