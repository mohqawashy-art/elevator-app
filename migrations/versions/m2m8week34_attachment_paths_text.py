"""توسيع أعمدة المرفقات لدعم عدة ملفات (JSON)

Revision ID: m2m8week34_attach_text
Revises: l1l7week33_revenue_title
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'm2m8week34_attach_text'
down_revision = 'l1l7week33_revenue_title'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c['name'] == column for c in sa.inspect(bind).get_columns(table))


def _alter_to_text(bind, table: str, column: str) -> None:
    if not _has_column(bind, table, column):
        return
    col = next(c for c in sa.inspect(bind).get_columns(table) if c['name'] == column)
    if isinstance(col['type'], sa.Text):
        return
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, type_=sa.Text(), existing_nullable=True)


def upgrade():
    bind = op.get_bind()
    _alter_to_text(bind, 'revenues', 'proof_path')
    _alter_to_text(bind, 'expenses', 'proof_path')
    _alter_to_text(bind, 'contracts', 'file_path')


def downgrade():
    bind = op.get_bind()
    for table, column in (
        ('revenues', 'proof_path'),
        ('expenses', 'proof_path'),
        ('contracts', 'file_path'),
    ):
        if not _has_column(bind, table, column):
            continue
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(column, type_=sa.String(300), existing_nullable=True)
