"""باقات SaaS: إضافات لكل مؤسسة + تجاوزات الحدود

Revision ID: w5w0week18_org_entitlements
Revises: v4v9week17_created_by
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'w5w0week18_org_entitlements'
down_revision = 'v4v9week17_created_by'
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
    if _has_table(bind, 'organizations'):
        with op.batch_alter_table('organizations') as batch_op:
            if not _has_column(bind, 'organizations', 'elevators_limit_override'):
                batch_op.add_column(sa.Column('elevators_limit_override', sa.Integer(), nullable=True))
            if not _has_column(bind, 'organizations', 'office_users_limit_override'):
                batch_op.add_column(sa.Column('office_users_limit_override', sa.Integer(), nullable=True))
            if not _has_column(bind, 'organizations', 'technicians_limit_override'):
                batch_op.add_column(sa.Column('technicians_limit_override', sa.Integer(), nullable=True))
            if not _has_column(bind, 'organizations', 'storage_gb_limit_override'):
                batch_op.add_column(sa.Column('storage_gb_limit_override', sa.Integer(), nullable=True))

    if not _has_table(bind, 'organization_addons'):
        op.create_table(
            'organization_addons',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
            sa.Column('addon_key', sa.String(length=50), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('unit_price_monthly', sa.Float(), nullable=True),
            sa.Column('status', sa.String(length=20), server_default='active'),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('starts_at', sa.DateTime(), nullable=True),
            sa.Column('ends_at', sa.DateTime(), nullable=True),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_organization_addons_organization_id', 'organization_addons', ['organization_id'])
        op.create_index('ix_organization_addons_addon_key', 'organization_addons', ['addon_key'])


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'organization_addons'):
        op.drop_index('ix_organization_addons_addon_key', table_name='organization_addons')
        op.drop_index('ix_organization_addons_organization_id', table_name='organization_addons')
        op.drop_table('organization_addons')
    if _has_table(bind, 'organizations'):
        with op.batch_alter_table('organizations') as batch_op:
            for col in (
                'elevators_limit_override',
                'office_users_limit_override',
                'technicians_limit_override',
                'storage_gb_limit_override',
            ):
                if _has_column(bind, 'organizations', col):
                    batch_op.drop_column(col)
