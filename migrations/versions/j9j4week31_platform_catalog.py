"""كتالوج الباقات الحي في لوحة المنصة

Revision ID: j9j4week31_platform_catalog
Revises: i8i3week30_contract_template
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'j9j4week31_platform_catalog'
down_revision = 'i8i3week30_contract_template'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'platform_catalog'):
        return
    op.create_table(
        'platform_catalog',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plans_json', sa.Text(), nullable=True),
        sa.Column('addons_json', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
    )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'platform_catalog'):
        op.drop_table('platform_catalog')
