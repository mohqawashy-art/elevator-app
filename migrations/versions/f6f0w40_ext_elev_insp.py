"""فحص مصعد خارجي — بوابة الفني

Revision ID: f6f0w40_ext_elev_insp
Revises: e5e0week39_maint_quote_survey
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'f6f0w40_ext_elev_insp'
down_revision = 'e5e0week39_maint_quote_survey'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'external_elevator_inspections'):
        return
    op.create_table(
        'external_elevator_inspections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('status', sa.String(30)),
        sa.Column('technician_id', sa.Integer(), sa.ForeignKey('technicians.id'), nullable=False),
        sa.Column('customer_name', sa.String(200)),
        sa.Column('customer_phone', sa.String(30)),
        sa.Column('city', sa.String(100)),
        sa.Column('district', sa.String(100)),
        sa.Column('address', sa.String(300)),
        sa.Column('building_name', sa.String(200)),
        sa.Column('elev_type', sa.String(100)),
        sa.Column('brand', sa.String(100)),
        sa.Column('model', sa.String(100)),
        sa.Column('capacity_kg', sa.Integer()),
        sa.Column('capacity_persons', sa.Integer()),
        sa.Column('floors', sa.Integer()),
        sa.Column('stops', sa.Integer()),
        sa.Column('serial_number', sa.String(100)),
        sa.Column('machine_type', sa.String(100)),
        sa.Column('door_type', sa.String(100)),
        sa.Column('control_type', sa.String(100)),
        sa.Column('condition_status', sa.String(80)),
        sa.Column('technical_opinion', sa.Text()),
        sa.Column('recommendations', sa.Text()),
        sa.Column('checklist_template_key', sa.String(50)),
        sa.Column('checklist_json', sa.Text()),
        sa.Column('inspected_at', sa.Date()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index(
        'ix_ext_elev_insp_technician_id',
        'external_elevator_inspections',
        ['technician_id'],
    )
    op.create_unique_constraint(
        'uq_ext_elev_insp_org_code',
        'external_elevator_inspections',
        ['organization_id', 'code'],
    )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'external_elevator_inspections'):
        op.drop_table('external_elevator_inspections')
