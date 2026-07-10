"""رقم ضريبي للعميل (ZATCA B2B)

Revision ID: l2j7week11customervat
Revises: k1i6week11zatcasecret
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'l2j7week11customervat'
down_revision = 'k1i6week11zatcasecret'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return column in {c['name'] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'customers', 'vat_number'):
        op.add_column('customers', sa.Column('vat_number', sa.String(length=50), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'customers', 'vat_number'):
        op.drop_column('customers', 'vat_number')
