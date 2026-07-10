"""عمود api_secret لاعتمادات زاتكا

Revision ID: k1i6week11zatcasecret
Revises: j0h5week11useruniq
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'k1i6week11zatcasecret'
down_revision = 'j0h5week11useruniq'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'zatca_credentials', 'api_secret'):
        op.add_column('zatca_credentials', sa.Column('api_secret', sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'zatca_credentials', 'api_secret'):
        op.drop_column('zatca_credentials', 'api_secret')
