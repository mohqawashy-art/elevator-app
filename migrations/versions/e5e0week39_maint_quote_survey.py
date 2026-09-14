"""فحص موقع عروض الصيانة

Revision ID: e5e0week39_maint_quote_survey
Revises: d4d9week38_field_geofence
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'e5e0week39_maint_quote_survey'
down_revision = 'd4d9week38_field_geofence'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'maintenance_quote_surveys'):
        op.create_table(
            'maintenance_quote_surveys',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True),
            sa.Column('quote_id', sa.Integer(), sa.ForeignKey('maintenance_quotes.id'), nullable=False),
            sa.Column('code', sa.String(20), nullable=False),
            sa.Column('status', sa.String(30)),
            sa.Column('technician_id', sa.Integer(), sa.ForeignKey('technicians.id'), nullable=False),
            sa.Column('request_notes', sa.Text()),
            sa.Column('requested_at', sa.DateTime()),
            sa.Column('started_at', sa.DateTime()),
            sa.Column('completed_at', sa.DateTime()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index('ix_maint_quote_surveys_quote_id', 'maintenance_quote_surveys', ['quote_id'])
        op.create_index('ix_maint_quote_surveys_technician_id', 'maintenance_quote_surveys', ['technician_id'])
        op.create_unique_constraint(
            'uq_maint_quote_survey_org_code',
            'maintenance_quote_surveys',
            ['organization_id', 'code'],
        )

    if not _has_table(bind, 'maintenance_quote_survey_units'):
        op.create_table(
            'maintenance_quote_survey_units',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True),
            sa.Column('survey_id', sa.Integer(), sa.ForeignKey('maintenance_quote_surveys.id'), nullable=False),
            sa.Column('sort_order', sa.Integer()),
            sa.Column('elevator_id', sa.Integer(), sa.ForeignKey('elevators.id'), nullable=True),
            sa.Column('unit_label', sa.String(80)),
            sa.Column('building_name', sa.String(200)),
            sa.Column('location_note', sa.String(200)),
            sa.Column('elev_type', sa.String(100)),
            sa.Column('brand', sa.String(100)),
            sa.Column('model', sa.String(100)),
            sa.Column('capacity_kg', sa.Integer()),
            sa.Column('capacity_persons', sa.Integer()),
            sa.Column('floors', sa.Integer()),
            sa.Column('stops', sa.Integer()),
            sa.Column('speed', sa.String(50)),
            sa.Column('machine_type', sa.String(30)),
            sa.Column('door_type', sa.String(50)),
            sa.Column('control_type', sa.String(50)),
            sa.Column('serial_number', sa.String(100)),
            sa.Column('technical_opinion', sa.Text()),
            sa.Column('condition_status', sa.String(40)),
            sa.Column('needs_repair', sa.Boolean()),
            sa.Column('needs_spare_parts', sa.Boolean()),
            sa.Column('repair_scope', sa.Text()),
            sa.Column('spare_parts_scope', sa.Text()),
            sa.Column('separate_quote_notes', sa.Text()),
            sa.Column('created_at', sa.DateTime()),
        )
        op.create_index(
            'ix_maint_quote_survey_units_survey_id',
            'maintenance_quote_survey_units',
            ['survey_id'],
        )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'maintenance_quote_survey_units'):
        op.drop_table('maintenance_quote_survey_units')
    if _has_table(bind, 'maintenance_quote_surveys'):
        op.drop_table('maintenance_quote_surveys')
