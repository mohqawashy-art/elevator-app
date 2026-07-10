"""إزالة unique العالمي على users.username — عزل per-tenant

Revision ID: j0h5week11useruniq
Revises: i9g4week11zatca2
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'j0h5week11useruniq'
down_revision = 'i9g4week11zatca2'
branch_labels = None
depends_on = None


def _unique_names(bind, table: str) -> set[str]:
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return set()
    names = {uq['name'] for uq in insp.get_unique_constraints(table) if uq.get('name')}
    # فهارس فريدة أيضاً
    for ix in insp.get_indexes(table):
        if ix.get('unique') and ix.get('name'):
            names.add(ix['name'])
    return names


def upgrade():
    bind = op.get_bind()
    if 'users' not in sa.inspect(bind).get_table_names():
        return

    dialect = bind.dialect.name
    existing = _unique_names(bind, 'users')

    # أسقاط القيد العالمي القديم إن وُجد — بدون try/except حتى لا تُجهض معاملة PostgreSQL
    for cname in ('users_username_key', 'username'):
        if cname not in existing:
            continue
        if dialect == 'postgresql':
            op.execute(sa.text(f'ALTER TABLE users DROP CONSTRAINT IF EXISTS {cname}'))
        else:
            op.drop_constraint(cname, 'users', type_='unique')

    existing = _unique_names(bind, 'users')
    if 'uq_user_org_username' not in existing:
        if dialect == 'postgresql':
            op.execute(sa.text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_user_org_username '
                'ON users (organization_id, username)'
            ))
        else:
            op.create_unique_constraint(
                'uq_user_org_username',
                'users',
                ['organization_id', 'username'],
            )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    existing = _unique_names(bind, 'users')
    if 'uq_user_org_username' in existing:
        if dialect == 'postgresql':
            op.execute(sa.text('DROP INDEX IF EXISTS uq_user_org_username'))
            op.execute(sa.text('ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_user_org_username'))
        else:
            op.drop_constraint('uq_user_org_username', 'users', type_='unique')
    if 'users_username_key' not in _unique_names(bind, 'users'):
        op.create_unique_constraint('users_username_key', 'users', ['username'])
