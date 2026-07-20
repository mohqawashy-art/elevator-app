"""جلسة واحدة لكل مستخدم مكتب — session_version

Revision ID: q9q4week14_session_version
Revises: p8p3week13wajourneyjson
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'q9q4week14_session_version'
down_revision = 'p8p3week13wajourneyjson'
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
    if _has_table(bind, 'users') and not _has_column(bind, 'users', 'session_version'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(
                sa.Column('session_version', sa.Integer(), nullable=False, server_default='0')
            )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'users') and _has_column(bind, 'users', 'session_version'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('session_version')
