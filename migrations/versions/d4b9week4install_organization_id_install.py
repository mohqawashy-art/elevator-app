"""organization_id على جداول موديول التركيب (أسبوع 4)

Revision ID: d4b9week4install
Revises: c3a8week3org
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'd4b9week4install'
down_revision = 'c3a8week3org'
branch_labels = None
depends_on = None

INSTALL_TABLES = (
    'installation_leads',
    'installation_projects',
    'installation_quotations',
    'installation_quotation_lines',
    'installation_timeline_steps',
)


def _table_exists(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    for table in INSTALL_TABLES:
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
    for table in reversed(INSTALL_TABLES):
        if not _table_exists(bind, table):
            continue
        cols = {c['name'] for c in sa.inspect(bind).get_columns(table)}
        if 'organization_id' not in cols:
            continue
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_organization_id', type_='foreignkey')
            batch_op.drop_index(f'ix_{table}_organization_id')
            batch_op.drop_column('organization_id')
