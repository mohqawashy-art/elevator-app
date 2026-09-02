"""إحداثيات موقع العقد — lat/lng/maps_url

Revision ID: z8z3week35_contract_location
Revises: m2m8week34_attach_text
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'z8z3week35_contract_loc'
down_revision = 'm2m8week34_attach_text'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c['name'] == column for c in insp.get_columns(table))


def upgrade():
    bind = op.get_bind()
    for col_name, col_type in (
        ('lat', sa.String(20)),
        ('lng', sa.String(20)),
        ('maps_url', sa.String(500)),
    ):
        if _has_column(bind, 'contracts', col_name):
            continue
        with op.batch_alter_table('contracts') as batch_op:
            batch_op.add_column(sa.Column(col_name, col_type, nullable=True))


def downgrade():
    bind = op.get_bind()
    for col_name in ('maps_url', 'lng', 'lat'):
        if not _has_column(bind, 'contracts', col_name):
            continue
        with op.batch_alter_table('contracts') as batch_op:
            batch_op.drop_column(col_name)
