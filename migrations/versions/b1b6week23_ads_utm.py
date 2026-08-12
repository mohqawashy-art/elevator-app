"""تتبع حملات الإعلانات لطلبات المبيعات (UTM / gclid)

Revision ID: b1b6week23ads_utm
Revises: a0a5week22sales_fulfill
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'b1b6week23ads_utm'
down_revision = 'a0a5week22sales_fulfill'
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
        if not _has_column(bind, 'sales_leads', 'utm_source'):
            batch_op.add_column(sa.Column('utm_source', sa.String(length=80), nullable=True))
        if not _has_column(bind, 'sales_leads', 'utm_medium'):
            batch_op.add_column(sa.Column('utm_medium', sa.String(length=80), nullable=True))
        if not _has_column(bind, 'sales_leads', 'utm_campaign'):
            batch_op.add_column(sa.Column('utm_campaign', sa.String(length=120), nullable=True))
        if not _has_column(bind, 'sales_leads', 'gclid'):
            batch_op.add_column(sa.Column('gclid', sa.String(length=120), nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'sales_leads'):
        return
    with op.batch_alter_table('sales_leads') as batch_op:
        for name in ('gclid', 'utm_campaign', 'utm_medium', 'utm_source'):
            if _has_column(bind, 'sales_leads', name):
                batch_op.drop_column(name)
