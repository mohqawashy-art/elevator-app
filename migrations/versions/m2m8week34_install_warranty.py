"""خيار ضمان عقود التركيب — install_warranty

Revision ID: m2m8week34_install_warranty
Revises: l1l7week33_revenue_title
Create Date: 2026-08-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'm2m8week34_install_warranty'
down_revision = 'l1l7week33_revenue_title'
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
    if not _has_table(bind, 'contracts'):
        return
    if not _has_column(bind, 'contracts', 'install_warranty'):
        op.add_column(
            'contracts',
            sa.Column('install_warranty', sa.String(length=30), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'contracts', 'install_warranty'):
        op.drop_column('contracts', 'install_warranty')
