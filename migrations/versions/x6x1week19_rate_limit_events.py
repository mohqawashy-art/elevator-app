"""جدول rate_limit_events لمشاركة الحدّ عبر workers

Revision ID: x6x1week19ratelimit
Revises: w5w0week18_org_entitlements
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'x6x1week19ratelimit'
down_revision = 'w5w0week18_org_entitlements'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'rate_limit_events'):
        return
    op.create_table(
        'rate_limit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('scope', sa.String(length=32), nullable=False),
        sa.Column('bucket_key', sa.String(length=191), nullable=False),
        sa.Column('created_at', sa.Float(), nullable=False),
    )
    op.create_index('ix_rate_limit_events_created_at', 'rate_limit_events', ['created_at'])
    op.create_index(
        'ix_rate_limit_scope_key_created',
        'rate_limit_events',
        ['scope', 'bucket_key', 'created_at'],
    )


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'rate_limit_events'):
        return
    op.drop_index('ix_rate_limit_scope_key_created', table_name='rate_limit_events')
    op.drop_index('ix_rate_limit_events_created_at', table_name='rate_limit_events')
    op.drop_table('rate_limit_events')
