"""سجل حركات العطل بين الفني والمكتب

Revision ID: h9h3w42_fault_events
Revises: g8h2w41_nasq_core_books
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'h9h3w42_fault_events'
down_revision = 'g8h2w41_nasq_core_books'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'fault_events'):
        return
    op.create_table(
        'fault_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('fault_id', sa.Integer(), sa.ForeignKey('faults.id'), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('detail', sa.Text()),
        sa.Column('actor_role', sa.String(length=20)),
        sa.Column('actor_name', sa.String(length=120)),
        sa.Column('created_at', sa.DateTime()),
    )
    op.create_index('ix_fault_events_organization_id', 'fault_events', ['organization_id'])
    op.create_index('ix_fault_events_fault_id', 'fault_events', ['fault_id'])
    op.create_index('ix_fault_events_created_at', 'fault_events', ['created_at'])


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'fault_events'):
        return
    op.drop_index('ix_fault_events_created_at', table_name='fault_events')
    op.drop_index('ix_fault_events_fault_id', table_name='fault_events')
    op.drop_index('ix_fault_events_organization_id', table_name='fault_events')
    op.drop_table('fault_events')
