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


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'users' not in insp.get_table_names():
        return

    # أسقاط القيد العالمي القديم إن وُجد
    for cname in ('users_username_key', 'username'):
        try:
            op.drop_constraint(cname, 'users', type_='unique')
        except Exception:
            pass

    # فهرس فريد مركّب (organization_id, username)
    existing = {ix['name'] for ix in insp.get_indexes('users')}
    uqs = {uq['name'] for uq in insp.get_unique_constraints('users')}
    if 'uq_user_org_username' not in existing and 'uq_user_org_username' not in uqs:
        op.create_unique_constraint(
            'uq_user_org_username',
            'users',
            ['organization_id', 'username'],
        )


def downgrade():
    try:
        op.drop_constraint('uq_user_org_username', 'users', type_='unique')
    except Exception:
        pass
    op.create_unique_constraint('users_username_key', 'users', ['username'])
