"""حقول ملف الفني — جنسية، خبرة، بريد، رخصة، أحياء

Revision ID: r0r5week15_tech_profile
Revises: q9q4week14_session_version
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = 'r0r5week15_tech_profile'
down_revision = 'q9q4week14_session_version'
branch_labels = None
depends_on = None

_COLS = (
    ('nationality', sa.String(100)),
    ('experience_years', sa.Integer()),
    ('email', sa.String(120)),
    ('national_id_expiry', sa.Date()),
    ('license_number', sa.String(50)),
    ('license_expiry', sa.Date()),
    ('districts_json', sa.Text()),
)


def _has_table(bind, name: str) -> bool:
    return name in sa.inspect(bind).get_table_names()


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return False
    return any(c['name'] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'technicians'):
        return
    missing = [(name, col_type) for name, col_type in _COLS if not _has_column(bind, 'technicians', name)]
    if not missing:
        return
    with op.batch_alter_table('technicians') as batch_op:
        for name, col_type in missing:
            batch_op.add_column(sa.Column(name, col_type, nullable=True))


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, 'technicians'):
        return
    present = [name for name, _ in _COLS if _has_column(bind, 'technicians', name)]
    if not present:
        return
    with op.batch_alter_table('technicians') as batch_op:
        for name in present:
            batch_op.drop_column(name)
