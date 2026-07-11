"""سجل مراحل واتساب على نفس كود البلاغ الوارد

Revision ID: p8p3week13wajourneyjson
Revises: p7o2week13wajourney
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'p8p3week13wajourneyjson'
down_revision = 'p7o2week13wajourney'
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
    if _has_table(bind, 'whatsapp_inbox') and not _has_column(bind, 'whatsapp_inbox', 'journey_json'):
        with op.batch_alter_table('whatsapp_inbox') as batch_op:
            batch_op.add_column(sa.Column('journey_json', sa.Text(), nullable=True))


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, 'whatsapp_inbox') and _has_column(bind, 'whatsapp_inbox', 'journey_json'):
        with op.batch_alter_table('whatsapp_inbox') as batch_op:
            batch_op.drop_column('journey_json')
