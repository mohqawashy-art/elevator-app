"""عروض أسعار عقود الصيانة

Revision ID: g6g1week28_sales_maint_quotes
Revises: f5f0week27_company_seal_layout
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'g6g1week28_sales_maint_quotes'
down_revision = 'f5f0week27_company_seal_layout'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'maintenance_quotes'):
        op.create_table(
            'maintenance_quotes',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True),
            sa.Column('code', sa.String(20), nullable=False),
            sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=False),
            sa.Column('status', sa.String(30)),
            sa.Column('duration_months', sa.Integer()),
            sa.Column('maint_frequency', sa.String(50)),
            sa.Column('visits_per_month', sa.Integer()),
            sa.Column('value', sa.Float()),
            sa.Column('tax_pct', sa.Float()),
            sa.Column('tax_amount', sa.Float()),
            sa.Column('total', sa.Float()),
            sa.Column('payment_terms', sa.String(50)),
            sa.Column('start_date', sa.Date()),
            sa.Column('end_date', sa.Date()),
            sa.Column('city', sa.String(100)),
            sa.Column('district', sa.String(100)),
            sa.Column('address', sa.Text()),
            sa.Column('notes', sa.Text()),
            sa.Column('result_contract_id', sa.Integer(), sa.ForeignKey('contracts.id')),
            sa.Column('approved_at', sa.DateTime()),
            sa.Column('sent_at', sa.DateTime()),
            sa.Column('created_at', sa.DateTime()),
            sa.Column('updated_at', sa.DateTime()),
        )
        op.create_index('ix_maintenance_quotes_customer_id', 'maintenance_quotes', ['customer_id'])
        op.create_unique_constraint('uq_maint_quote_org_code', 'maintenance_quotes', ['organization_id', 'code'])

    if not _has_table(bind, 'maintenance_quote_elevators'):
        op.create_table(
            'maintenance_quote_elevators',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True),
            sa.Column('quote_id', sa.Integer(), sa.ForeignKey('maintenance_quotes.id'), nullable=False),
            sa.Column('elevator_id', sa.Integer(), sa.ForeignKey('elevators.id'), nullable=False),
        )
        op.create_index('ix_maintenance_quote_elevators_quote_id', 'maintenance_quote_elevators', ['quote_id'])


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'maintenance_quote_elevators'):
        op.drop_table('maintenance_quote_elevators')
    if _has_table(bind, 'maintenance_quotes'):
        op.drop_table('maintenance_quotes')
