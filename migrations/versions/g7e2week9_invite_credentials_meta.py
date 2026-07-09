"""حقول بيانات الدخول على دعوات الانضمام

Revision ID: g7e2week9creds
Revises: f6d1week9onboard
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'g7e2week9creds'
down_revision = 'f6d1week9onboard'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('onboarding_invites', sa.Column('admin_username', sa.String(length=50), nullable=True))
    op.add_column('onboarding_invites', sa.Column('login_url', sa.String(length=300), nullable=True))
    op.add_column('onboarding_invites', sa.Column('credentials_email_sent_at', sa.DateTime(), nullable=True))
    op.add_column('onboarding_invites', sa.Column('credentials_email_error', sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column('onboarding_invites', 'credentials_email_error')
    op.drop_column('onboarding_invites', 'credentials_email_sent_at')
    op.drop_column('onboarding_invites', 'login_url')
    op.drop_column('onboarding_invites', 'admin_username')
