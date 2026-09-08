"""بروتوكول الجهاز — توافق متعدد

Revision ID: c3c8week37_attendance_protocol
Revises: b2b7week36_attendance
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'c3c8week37_attendance_protocol'
down_revision = 'b2b7week36_attendance'
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, 'biometric_devices', 'protocol'):
        op.add_column(
            'biometric_devices',
            sa.Column('protocol', sa.String(length=32), nullable=True),
        )
        op.execute("UPDATE biometric_devices SET protocol = 'adms_zkteco' WHERE protocol IS NULL")
    if not _has_column(bind, 'biometric_devices', 'auto_registered'):
        op.add_column(
            'biometric_devices',
            sa.Column('auto_registered', sa.Boolean(), nullable=True),
        )
        op.execute('UPDATE biometric_devices SET auto_registered = false WHERE auto_registered IS NULL')
    op.create_index(
        'ix_biometric_devices_auth_token',
        'biometric_devices',
        ['auth_token'],
        unique=False,
    )


def downgrade():
    bind = op.get_bind()
    op.drop_index('ix_biometric_devices_auth_token', table_name='biometric_devices')
    if _has_column(bind, 'biometric_devices', 'auto_registered'):
        op.drop_column('biometric_devices', 'auto_registered')
    if _has_column(bind, 'biometric_devices', 'protocol'):
        op.drop_column('biometric_devices', 'protocol')
