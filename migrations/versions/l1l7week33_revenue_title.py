"""بيان الإيراد — عمود title

Revision ID: l1l7week33_revenue_title
Revises: k0k5week32_org_features
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'l1l7week33_revenue_title'
down_revision = 'k0k5week32_org_features'
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
    if not _has_table(bind, 'revenues'):
        return
    if not _has_column(bind, 'revenues', 'title'):
        op.add_column('revenues', sa.Column('title', sa.String(length=300), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'revenues', 'title'):
        op.drop_column('revenues', 'title')
