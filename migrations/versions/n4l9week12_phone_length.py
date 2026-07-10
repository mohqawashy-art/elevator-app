"""توسيع أعمدة الهاتف للعملاء/الفنيين لاستيعاب التنسيق الدولي

Revision ID: n4l9week12phonelen
Revises: m3k8week12tenantcode
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'n4l9week12phonelen'
down_revision = 'm3k8week12tenantcode'
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
    for table, cols in (
        ('customers', ('phone', 'phone2')),
        ('technicians', ('phone', 'phone2')),
    ):
        if not _has_table(bind, table):
            continue
        with op.batch_alter_table(table) as batch_op:
            for col in cols:
                if _col_type(bind, table, col) is None:
                    continue
                batch_op.alter_column(
                    col,
                    existing_type=sa.String(length=20),
                    type_=sa.String(length=40),
                    existing_nullable=True,
                )


def downgrade():
    bind = op.get_bind()
    for table, cols in (
        ('customers', ('phone', 'phone2')),
        ('technicians', ('phone', 'phone2')),
    ):
        if not _has_table(bind, table):
            continue
        with op.batch_alter_table(table) as batch_op:
            for col in cols:
                if _col_type(bind, table, col) is None:
                    continue
                batch_op.alter_column(
                    col,
                    existing_type=sa.String(length=40),
                    type_=sa.String(length=20),
                    existing_nullable=True,
                )
