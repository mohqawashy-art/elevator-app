"""جدول دعوات الانضمام — لوحة المشغّل

Revision ID: f6d1week9onboard
Revises: e5c0week6zatca
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'f6d1week9onboard'
down_revision = 'e5c0week6zatca'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'onboarding_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('plan', sa.String(length=30), nullable=True),
        sa.Column('suggested_slug', sa.String(length=63), nullable=True),
        sa.Column('contact_email', sa.String(length=100), nullable=True),
        sa.Column('contact_name', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('company_name_en', sa.String(length=200), nullable=True),
        sa.Column('cr_number', sa.String(length=50), nullable=True),
        sa.Column('vat_number', sa.String(length=50), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('admin_name', sa.String(length=100), nullable=True),
        sa.Column('admin_email', sa.String(length=100), nullable=True),
        sa.Column('admin_phone', sa.String(length=30), nullable=True),
        sa.Column('preferred_slug', sa.String(length=63), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_onboarding_invites_token', 'onboarding_invites', ['token'], unique=False)


def downgrade():
    op.drop_index('ix_onboarding_invites_token', table_name='onboarding_invites')
    op.drop_table('onboarding_invites')
