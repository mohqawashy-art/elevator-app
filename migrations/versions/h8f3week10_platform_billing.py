"""اشتراك المنصة + سجل الدفعات

Revision ID: h8f3week10billing
Revises: g7e2week9creds
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'h8f3week10billing'
down_revision = 'g7e2week9creds'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('organizations', sa.Column('billing_cycle', sa.String(length=20), nullable=True))
    op.add_column('organizations', sa.Column('billing_amount', sa.Float(), nullable=True))
    op.add_column('organizations', sa.Column('billing_status', sa.String(length=20), nullable=True))
    op.add_column('organizations', sa.Column('current_period_start', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('current_period_end', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('last_payment_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('last_payment_amount', sa.Float(), nullable=True))
    op.add_column('organizations', sa.Column('last_payment_ref', sa.String(length=100), nullable=True))
    op.add_column('organizations', sa.Column('billing_notes', sa.Text(), nullable=True))

    op.create_table(
        'platform_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('method', sa.String(length=40), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('plan', sa.String(length=30), nullable=True),
        sa.Column('recorded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_platform_payments_organization_id', 'platform_payments', ['organization_id'])


def downgrade():
    op.drop_index('ix_platform_payments_organization_id', table_name='platform_payments')
    op.drop_table('platform_payments')
    op.drop_column('organizations', 'billing_notes')
    op.drop_column('organizations', 'last_payment_ref')
    op.drop_column('organizations', 'last_payment_amount')
    op.drop_column('organizations', 'last_payment_at')
    op.drop_column('organizations', 'current_period_end')
    op.drop_column('organizations', 'current_period_start')
    op.drop_column('organizations', 'billing_status')
    op.drop_column('organizations', 'billing_amount')
    op.drop_column('organizations', 'billing_cycle')
