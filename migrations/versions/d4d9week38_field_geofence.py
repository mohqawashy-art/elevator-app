"""إعدادات تحقق موقع الفني (geofence)

Revision ID: d4d9week38_field_geofence
Revises: c3c8week37_attendance_protocol
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'd4d9week38_field_geofence'
down_revision = 'c3c8week37_attendance_protocol'
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
    if not _has_column(bind, 'settings', 'field_geofence_enabled'):
        op.add_column(
            'settings',
            sa.Column('field_geofence_enabled', sa.Boolean(), nullable=True, server_default=sa.true()),
        )
    if not _has_column(bind, 'settings', 'field_geofence_radius_m'):
        op.add_column(
            'settings',
            sa.Column('field_geofence_radius_m', sa.Integer(), nullable=True, server_default='300'),
        )


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, 'settings', 'field_geofence_radius_m'):
        op.drop_column('settings', 'field_geofence_radius_m')
    if _has_column(bind, 'settings', 'field_geofence_enabled'):
        op.drop_column('settings', 'field_geofence_enabled')
