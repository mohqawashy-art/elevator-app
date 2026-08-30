"""تجاوز ميزات باقة التخصيص لكل مؤسسة

Revision ID: k0k5week32_org_features
Revises: j9j4week31_platform_catalog
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'k0k5week32_org_features'
down_revision = 'j9j4week31_platform_catalog'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    if table not in sa.inspect(bind).get_table_names():
        return False
    return column in {c['name'] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'organizations', 'features_override_json'):
        op.add_column('organizations', sa.Column('features_override_json', sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'organizations', 'features_override_json'):
        op.drop_column('organizations', 'features_override_json')
