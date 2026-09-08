"""الحضور والانصراف — موظفون، فروع، أجهزة ZKTeco

Revision ID: b2b7week36_attendance
Revises: z8z3week35_contract_loc
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'b2b7week36_attendance'
down_revision = 'z8z3week35_contract_loc'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'attendance_branches'):
        return

    op.create_table(
        'attendance_branches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('name_en', sa.String(length=120), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_attendance_branch_org_code'),
    )
    op.create_index(
        'ix_attendance_branches_organization_id',
        'attendance_branches',
        ['organization_id'],
    )

    op.create_table(
        'attendance_employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_en', sa.String(length=100), nullable=True),
        sa.Column('job_title', sa.String(length=100), nullable=True),
        sa.Column('department', sa.String(length=100), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('technician_id', sa.Integer(), nullable=True),
        sa.Column('biometric_user_id', sa.String(length=20), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('national_id', sa.String(length=20), nullable=True),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('salary', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['attendance_branches.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['technician_id'], ['technicians.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_attendance_employee_org_code'),
        sa.UniqueConstraint(
            'organization_id', 'biometric_user_id',
            name='uq_attendance_employee_org_bio_id',
        ),
    )
    op.create_index(
        'ix_attendance_employees_organization_id',
        'attendance_employees',
        ['organization_id'],
    )

    op.create_table(
        'biometric_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),
        sa.Column('serial_number', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('auth_token', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_ip', sa.String(length=45), nullable=True),
        sa.Column('firmware', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['branch_id'], ['attendance_branches.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('serial_number', name='uq_biometric_device_serial'),
    )
    op.create_index(
        'ix_biometric_devices_organization_id',
        'biometric_devices',
        ['organization_id'],
    )

    op.create_table(
        'attendance_punches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('biometric_user_id', sa.String(length=20), nullable=False),
        sa.Column('punched_at', sa.DateTime(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('verify_mode', sa.Integer(), nullable=True),
        sa.Column('work_code', sa.Integer(), nullable=True),
        sa.Column('raw_line', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['device_id'], ['biometric_devices.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['attendance_employees.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'device_id', 'biometric_user_id', 'punched_at',
            name='uq_attendance_punch_device_user_time',
        ),
    )
    op.create_index(
        'ix_attendance_punches_organization_id',
        'attendance_punches',
        ['organization_id'],
    )
    op.create_index('ix_attendance_punches_punched_at', 'attendance_punches', ['punched_at'])

    op.create_table(
        'attendance_days',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('check_in', sa.DateTime(), nullable=True),
        sa.Column('check_out', sa.DateTime(), nullable=True),
        sa.Column('late_minutes', sa.Integer(), nullable=True),
        sa.Column('early_leave_minutes', sa.Integer(), nullable=True),
        sa.Column('worked_minutes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('shift_start', sa.String(length=5), nullable=True),
        sa.Column('shift_end', sa.String(length=5), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['attendance_employees.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'organization_id', 'employee_id', 'work_date',
            name='uq_attendance_day_org_employee_date',
        ),
    )
    op.create_index(
        'ix_attendance_days_organization_id',
        'attendance_days',
        ['organization_id'],
    )
    op.create_index('ix_attendance_days_work_date', 'attendance_days', ['work_date'])


def downgrade():
    bind = op.get_bind()
    for table in (
        'attendance_days',
        'attendance_punches',
        'biometric_devices',
        'attendance_employees',
        'attendance_branches',
    ):
        if _has_table(bind, table):
            op.drop_table(table)
