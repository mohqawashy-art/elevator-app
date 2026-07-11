"""وارد واتساب + إعدادات استقبال المكتب

Revision ID: p6n1week13wa
Revises: o5m0week12reflen
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'p6n1week13wa'
down_revision = 'o5m0week12reflen'
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c['name'] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()
    if _has_table(bind, 'settings'):
        with op.batch_alter_table('settings') as batch_op:
            if not _has_column(bind, 'settings', 'whatsapp_phone'):
                batch_op.add_column(sa.Column('whatsapp_phone', sa.String(length=40), nullable=True))
            if not _has_column(bind, 'settings', 'whatsapp_receive_mode'):
                batch_op.add_column(
                    sa.Column('whatsapp_receive_mode', sa.String(length=20), nullable=True)
                )

    if not _has_table(bind, 'whatsapp_inbox'):
        op.create_table(
            'whatsapp_inbox',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('direction', sa.String(length=20)),
            sa.Column('from_phone', sa.String(length=40), nullable=False),
            sa.Column('from_name', sa.String(length=120)),
            sa.Column('body', sa.Text()),
            sa.Column('media_url', sa.String(length=500)),
            sa.Column('status', sa.String(length=40)),
            sa.Column('receive_target', sa.String(length=40)),
            sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id')),
            sa.Column('elevator_id', sa.Integer(), sa.ForeignKey('elevators.id')),
            sa.Column('fault_id', sa.Integer(), sa.ForeignKey('faults.id')),
            sa.Column('wa_message_id', sa.String(length=120)),
            sa.Column('received_at', sa.DateTime()),
            sa.Column('notes', sa.Text()),
            sa.Column('created_at', sa.DateTime()),
            sa.UniqueConstraint('organization_id', 'code', name='uq_whatsapp_inbox_org_code'),
        )
        op.create_index('ix_whatsapp_inbox_organization_id', 'whatsapp_inbox', ['organization_id'])


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'whatsapp_inbox'):
        op.drop_index('ix_whatsapp_inbox_organization_id', table_name='whatsapp_inbox')
        op.drop_table('whatsapp_inbox')
    if _has_table(bind, 'settings'):
        with op.batch_alter_table('settings') as batch_op:
            if _has_column(bind, 'settings', 'whatsapp_receive_mode'):
                batch_op.drop_column('whatsapp_receive_mode')
            if _has_column(bind, 'settings', 'whatsapp_phone'):
                batch_op.drop_column('whatsapp_phone')
