"""نموذج عقد Word في إعدادات الشركة

Revision ID: i8i3week30_contract_template
Revises: h7h2week29_estimate_quote_link
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'i8i3week30_contract_template'
down_revision = 'h7h2week29_estimate_quote_link'
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
    if not _has_column(bind, 'settings', 'contract_template_path'):
        op.add_column('settings', sa.Column('contract_template_path', sa.String(length=300), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'settings', 'contract_template_path'):
        op.drop_column('settings', 'contract_template_path')
