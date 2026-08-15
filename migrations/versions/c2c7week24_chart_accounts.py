"""شجرة الحسابات + ربط account_id للإيرادات/المصروفات

Revision ID: c2c7week24_chart_accounts
Revises: b1b6week23ads_utm
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'c2c7week24_chart_accounts'
down_revision = 'b1b6week23ads_utm'
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
    if not _has_table(bind, 'accounts'):
        op.create_table(
            'accounts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=True, index=True),
            sa.Column('code', sa.String(length=20), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('name_en', sa.String(length=200), nullable=True),
            sa.Column('account_type', sa.String(length=20), nullable=False),
            sa.Column('parent_id', sa.Integer(), sa.ForeignKey('accounts.id'), nullable=True),
            sa.Column('map_key', sa.String(length=80), nullable=True),
            sa.Column('is_postable', sa.Boolean(), nullable=True),
            sa.Column('is_system', sa.Boolean(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('sort_order', sa.Integer(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('organization_id', 'code', name='uq_account_org_code'),
        )

    if _has_table(bind, 'revenues') and not _has_column(bind, 'revenues', 'account_id'):
        with op.batch_alter_table('revenues') as batch_op:
            batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_revenues_account_id', 'accounts', ['account_id'], ['id']
            )
            batch_op.create_index('ix_revenues_account_id', ['account_id'])

    if _has_table(bind, 'expenses') and not _has_column(bind, 'expenses', 'account_id'):
        with op.batch_alter_table('expenses') as batch_op:
            batch_op.add_column(sa.Column('account_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_expenses_account_id', 'accounts', ['account_id'], ['id']
            )
            batch_op.create_index('ix_expenses_account_id', ['account_id'])


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'revenues') and _has_column(bind, 'revenues', 'account_id'):
        with op.batch_alter_table('revenues') as batch_op:
            batch_op.drop_constraint('fk_revenues_account_id', type_='foreignkey')
            batch_op.drop_index('ix_revenues_account_id')
            batch_op.drop_column('account_id')
    if _has_table(bind, 'expenses') and _has_column(bind, 'expenses', 'account_id'):
        with op.batch_alter_table('expenses') as batch_op:
            batch_op.drop_constraint('fk_expenses_account_id', type_='foreignkey')
            batch_op.drop_index('ix_expenses_account_id')
            batch_op.drop_column('account_id')
    if _has_table(bind, 'accounts'):
        op.drop_table('accounts')
