"""طلبات التجربة وعروض السعر من صفحات التسويق

Revision ID: z9z4week21sales_leads
Revises: y7y2week20cust_phones
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'z9z4week21sales_leads'
down_revision = 'y7y2week20cust_phones'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'sales_leads'):
        return
    op.create_table(
        'sales_leads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_type', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('contact_name', sa.String(length=100), nullable=False),
        sa.Column('contact_email', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=40), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('elevators', sa.String(length=40), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source_path', sa.String(length=40), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=True),
        sa.Column('email_error', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_sales_leads_contact_email', 'sales_leads', ['contact_email'])
    op.create_index('ix_sales_leads_created_at', 'sales_leads', ['created_at'])


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'sales_leads'):
        return
    op.drop_index('ix_sales_leads_created_at', table_name='sales_leads')
    op.drop_index('ix_sales_leads_contact_email', table_name='sales_leads')
    op.drop_table('sales_leads')
