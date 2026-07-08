"""organization_id على جداول النواة + organizations

Revision ID: c3a8week3org
Revises: 05f79b5de987
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'c3a8week3org'
down_revision = '05f79b5de987'
branch_labels = None
depends_on = None

TENANT_TABLES = (
    'customers', 'elevators', 'contracts', 'contract_elevators',
    'technicians', 'technician_documents', 'maintenance_teams',
    'maintenance_visits', 'visit_technicians', 'faults', 'fault_technicians',
    'revenues', 'expenses', 'invoices', 'inventory_items', 'stock_movements',
    'parts_billing', 'purchase_orders', 'purchase_order_lines',
    'elevator_estimates', 'elevator_estimate_lines', 'signatories',
    'settings', 'users', 'audit_logs',
)


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if not _table_exists(bind, 'organizations'):
        op.create_table(
            'organizations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('slug', sa.String(length=63), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('name_en', sa.String(length=200), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('plan', sa.String(length=30), nullable=True),
            sa.Column('admin_email', sa.String(length=100), nullable=True),
            sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('suspended_at', sa.DateTime(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('slug'),
        )
        with op.batch_alter_table('organizations', schema=None) as batch_op:
            batch_op.create_index('ix_organizations_slug', ['slug'], unique=False)

    op.execute(sa.text(
        "INSERT INTO organizations (slug, name, status, plan) "
        "SELECT 'default', 'LiftCore Default', 'active', 'basic' "
        "WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE slug = 'default')"
    ))

    for table in TENANT_TABLES:
        if not _table_exists(bind, table):
            continue
        cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
        if 'organization_id' in cols:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        op.execute(sa.text(
            f'UPDATE {table} SET organization_id = '
            f"(SELECT id FROM organizations WHERE slug = 'default' LIMIT 1) "
            f'WHERE organization_id IS NULL'
        ))
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('organization_id', nullable=False)
            batch_op.create_foreign_key(
                f'fk_{table}_organization_id',
                'organizations',
                ['organization_id'],
                ['id'],
            )
            batch_op.create_index(
                f'ix_{table}_organization_id',
                ['organization_id'],
                unique=False,
            )


def downgrade():
    bind = op.get_bind()
    for table in reversed(TENANT_TABLES):
        if not _table_exists(bind, table):
            continue
        cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
        if 'organization_id' not in cols:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_organization_id', type_='foreignkey')
            batch_op.drop_index(f'ix_{table}_organization_id')
            batch_op.drop_column('organization_id')
    if _table_exists(bind, 'organizations'):
        op.drop_table('organizations')
